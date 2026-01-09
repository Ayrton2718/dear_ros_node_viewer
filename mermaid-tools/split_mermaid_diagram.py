#!/usr/bin/env python3
"""
Script to split a large Mermaid diagram into subgraphs based on node namespaces.
"""

import re
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple


def parse_mermaid_file(file_path: str) -> Tuple[List[str], Dict[str, str], List[str]]:
    """
    Parse a Mermaid diagram file and extract header, nodes, and connections.
    Supports both .md (markdown) and .html files.
    Handles linked nodes like: A([<a class="internal-link" href="...">node_name</a>])
    
    Returns:
        Tuple of (header_lines, node_definitions, connections)
        node_definitions maps node_id to the full node definition (with or without links)
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Try to extract from HTML first (look for content within <pre class="mermaid">)
    html_match = re.search(r'<pre class="mermaid">\s*(.*?)\s*</pre>', content, re.DOTALL)
    if html_match:
        mermaid_content = html_match.group(1)
    else:
        # Fall back to markdown format
        mermaid_match = re.search(r'```mermaid\n(.*?)\n```', content, re.DOTALL)
        if not mermaid_match:
            raise ValueError("No mermaid diagram found in file (neither HTML nor markdown format)")
        mermaid_content = mermaid_match.group(1)
    
    lines = mermaid_content.split('\n')
    
    header_lines = []
    node_definitions = {}
    connections = []
    
    in_header = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Detect header section (config)
        if line == '---':
            in_header = not in_header
            header_lines.append(line)
            continue
        
        if in_header or line.startswith('config:') or line.startswith('layout:') or \
           line.startswith('look:') or line.startswith('theme:') or line.startswith('graph '):
            header_lines.append(line)
            continue
        
        # Parse node definitions: A([/node/name]) or A([<a ...>node_name</a>])
        node_match = re.match(r'^([A-Z]+)\(\[\s*(.*?)\s*\]\)$', line)
        if node_match:
            node_id = node_match.group(1)
            node_content = node_match.group(2)
            # Store the full node content (with link if present)
            node_definitions[node_id] = node_content
            continue
        
        # Parse style definitions: style A fill:#color
        if line.startswith('style '):
            # We'll handle styles separately
            continue
        
        # Parse connections: A -->|/topic| B or A --> B
        if '-->' in line:
            connections.append(line)
    
    return header_lines, node_definitions, connections


def extract_plain_node_name(node_content: str) -> str:
    """
    Extract the plain node name from node content, handling HTML links.
    Examples:
        '<a class="internal-link" href="...">node_name</a>' -> 'node_name'
        '/simple/node/name' -> '/simple/node/name'
    """
    # Check if it's a linked node
    link_match = re.search(r'<a[^>]*>([^<]+)</a>', node_content)
    if link_match:
        return link_match.group(1)
    return node_content


def extract_namespace(node_content: str) -> str:
    """
    Extract the namespace from a ROS node name with detailed splitting for specific modules.
    Only specified namespaces are preserved, others are classified as /other.
    Handles both plain node names and linked nodes with HTML.
    Examples:
        /adapi/node/autoware_state -> /adapi
        /control/vehicle_cmd_gate -> /control
        /system/service_log_checker -> /system
        /planning/scenario_planning/validator -> /planning/scenario_planning
        /planning/mission_planning/mission_planner -> /planning/mission_planning
        /some_other/node -> /other
        '<a ...>/sensing/imu/gyro_bias_validator</a>' -> /sensing
    """
    # Extract plain node name from content
    node_name = extract_plain_node_name(node_content)
    
    parts = node_name.strip('/').split('/')
    
    if len(parts) == 0:
        return '/other'
    
    # Define the allowed top-level namespaces
    allowed_namespaces = {
        'control', 'planning', 'system', 'adapi', 
        'localization', 'perception', 'sensing', 'tier4_api'
    }
    
    first_level = parts[0]
    
    # Check if first level is in allowed namespaces
    if first_level not in allowed_namespaces:
        return '/other'
    
    # Special handling for planning modules - extract two levels
    if len(parts) >= 2 and first_level == 'planning':
        if parts[1] in ['scenario_planning']:
            return '/' + '/'.join(parts[:2])
    
    # For other allowed namespaces, extract first level only
    return '/' + first_level


def group_nodes_by_namespace(node_definitions: Dict[str, str]) -> Dict[str, List[Tuple[str, str]]]:
    """
    Group nodes by their namespace.
    
    Returns:
        Dict mapping namespace to list of (node_id, node_content) tuples
        node_content includes the full definition (with links if present)
    """
    namespace_groups = {}
    
    for node_id, node_content in node_definitions.items():
        namespace = extract_namespace(node_content)
        if namespace not in namespace_groups:
            namespace_groups[namespace] = []
        namespace_groups[namespace].append((node_id, node_content))
    
    return namespace_groups


def get_node_styles(file_path: str) -> Dict[str, str]:
    """Extract style definitions for each node."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    styles = {}
    for line in content.split('\n'):
        style_match = re.match(r'^style ([A-Z]+) (.+)$', line.strip())
        if style_match:
            node_id = style_match.group(1)
            style_def = style_match.group(2)
            styles[node_id] = style_def
    
    return styles


def get_node_colors(file_path: str) -> Dict[str, str]:
    """Extract fill colors for each node from style definitions."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    colors = {}
    for line in content.split('\n'):
        style_match = re.match(r'^style ([A-Z]+) (.+)$', line.strip())
        if style_match:
            node_id = style_match.group(1)
            style_def = style_match.group(2)
            # Extract fill color from style definition
            fill_match = re.search(r'fill:(#[0-9a-fA-F]{6})', style_def)
            if fill_match:
                colors[node_id] = fill_match.group(1)
    
    return colors


def classify_connections(connections: List[str], namespace_groups: Dict[str, List[Tuple[str, str]]]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Classify connections as internal (within subgraph) or external (between subgraphs).
    
    Returns:
        Tuple of (external_connections, internal_connections_by_namespace)
    """
    # Create a mapping from node_id to namespace
    node_to_namespace = {}
    for namespace, nodes in namespace_groups.items():
        for node_id, _ in nodes:
            node_to_namespace[node_id] = namespace
    
    external_connections = []
    internal_connections = {ns: [] for ns in namespace_groups.keys()}
    
    for conn in connections:
        # Extract source and target node IDs from connection
        # Format: A -->|/topic| B or A --> B
        match = re.match(r'^([A-Z]+)\s+-->', conn)
        if not match:
            continue
        
        source = match.group(1)
        # Find target node (last capital letter sequence)
        targets = re.findall(r'([A-Z]+)(?:\s|$)', conn)
        if len(targets) < 2:
            continue
        
        target = targets[-1]
        
        source_ns = node_to_namespace.get(source)
        target_ns = node_to_namespace.get(target)
        
        if source_ns and target_ns:
            if source_ns == target_ns:
                # Internal connection
                internal_connections[source_ns].append(conn)
            else:
                # External connection
                external_connections.append(conn)
    
    return external_connections, internal_connections


def generate_individual_subgraph_mermaid(
    target_namespace: str,
    namespace_groups: Dict[str, List[Tuple[str, str]]],
    all_connections: List[str],
    node_definitions: Dict[str, str],
    styles: Dict[str, str],
    colors: Dict[str, str],
    header_lines: List[str]
) -> str:
    """
    Generate a Mermaid diagram for a single namespace with external nodes collapsed.
    
    Args:
        target_namespace: The namespace to generate the diagram for
        namespace_groups: All namespace groups
        all_connections: All connections in the original diagram
        node_definitions: Mapping of node_id to node_name
        styles: Style definitions for nodes
        colors: Fill colors for nodes
        header_lines: Header lines from the original diagram
    
    Returns:
        Mermaid diagram content as string
    """
    output_lines = []
    
    # Add header
    for line in header_lines:
        output_lines.append(line)
    
    output_lines.append('')
    
    # Create a mapping from node_id to namespace
    node_to_namespace = {}
    for namespace, nodes in namespace_groups.items():
        for node_id, _ in nodes:
            node_to_namespace[node_id] = namespace
    
    # Get nodes in target namespace
    target_nodes = {node_id: node_content for node_id, node_content in namespace_groups[target_namespace]}
    
    # Track which external namespaces we need
    external_namespaces_used = set()
    
    # Parse connections to find which external namespaces are connected
    for conn in all_connections:
        # Extract source and target node IDs
        match = re.match(r'^([A-Z]+)\s+-->', conn)
        if not match:
            continue
        
        source = match.group(1)
        targets = re.findall(r'([A-Z]+)(?:\s|$)', conn)
        if len(targets) < 2:
            continue
        
        target = targets[-1]
        
        source_ns = node_to_namespace.get(source)
        target_ns = node_to_namespace.get(target)
        
        # Check if this connection involves the target namespace
        if source_ns == target_namespace and target_ns != target_namespace:
            external_namespaces_used.add(target_ns)
        elif target_ns == target_namespace and source_ns != target_namespace:
            external_namespaces_used.add(source_ns)
    
    # Create collapsed nodes for external namespaces
    collapsed_nodes = {}  # namespace -> collapsed_node_id
    next_node_id = 0
    
    for ext_ns in sorted(external_namespaces_used):
        # Generate a unique node ID for this namespace
        node_id = f"NS{next_node_id}"
        next_node_id += 1
        collapsed_nodes[ext_ns] = node_id
    
    # Add collapsed external namespace nodes (outside subgraph)
    for ext_ns in sorted(external_namespaces_used):
        node_id = collapsed_nodes[ext_ns]
        output_lines.append(f'{node_id}([{ext_ns}])')
    
    output_lines.append('')
    
    # Add target namespace as a subgraph
    subgraph_name = target_namespace.replace('/', '_').strip('_')
    output_lines.append(f'subgraph {subgraph_name}["{target_namespace}"]')
    
    # Add target namespace nodes inside subgraph
    # Sort by plain node name for consistent ordering
    for node_id, node_content in sorted(target_nodes.items(), key=lambda x: extract_plain_node_name(x[1])):
        output_lines.append(f'    {node_id}([{node_content}])')
    
    output_lines.append('')
    
    # Add styles for target namespace nodes
    for node_id in target_nodes.keys():
        if node_id in styles:
            output_lines.append(f'    style {node_id} {styles[node_id]}')
    
    output_lines.append('end')
    output_lines.append('')
    
    # Add styles for collapsed nodes (use color from representative node)
    for ext_ns, collapsed_node_id in collapsed_nodes.items():
        # Get the first node from this namespace as representative
        if ext_ns in namespace_groups and len(namespace_groups[ext_ns]) > 0:
            representative_node_id = namespace_groups[ext_ns][0][0]
            if representative_node_id in colors:
                color = colors[representative_node_id]
                output_lines.append(f'style {collapsed_node_id} fill:{color},stroke:#666,stroke-width:2px')
            else:
                output_lines.append(f'style {collapsed_node_id} fill:#e0e0e0,stroke:#666,stroke-width:2px')
        else:
            output_lines.append(f'style {collapsed_node_id} fill:#e0e0e0,stroke:#666,stroke-width:2px')
    
    output_lines.append('')
    
    # Process connections
    processed_connections = []  # List to maintain order
    processed_set = set()  # Set for duplicate checking
    
    for conn in all_connections:
        # Extract source and target node IDs and topic
        match = re.match(r'^([A-Z]+)\s+-->(\|[^|]+\|)?\s*([A-Z]+)', conn)
        if not match:
            continue
        
        source = match.group(1)
        topic = match.group(2) if match.group(2) else ''
        target = match.group(3)
        
        source_ns = node_to_namespace.get(source)
        target_ns = node_to_namespace.get(target)
        
        # Only include connections involving the target namespace
        if source_ns != target_namespace and target_ns != target_namespace:
            continue
        
        # Map nodes to collapsed versions if needed
        new_source = source if source_ns == target_namespace else collapsed_nodes.get(source_ns)
        new_target = target if target_ns == target_namespace else collapsed_nodes.get(target_ns)
        
        if new_source and new_target:
            new_conn = f'{new_source} -->{topic} {new_target}'
            if new_conn not in processed_set:
                output_lines.append(new_conn)
                processed_connections.append((new_conn, source))  # Store with original source for color
                processed_set.add(new_conn)
    
    # Add linkStyle declarations with colors
    output_lines.append('')
    output_lines.append('%% Link styles with source node colors')
    for link_index, (conn, original_source) in enumerate(processed_connections):
        if original_source in colors:
            color = colors[original_source]
            output_lines.append(f'linkStyle {link_index} stroke:{color},stroke-width:2px')
    
    return '\n'.join(output_lines)


def export_individual_subgraphs(
    namespace_groups: Dict[str, List[Tuple[str, str]]],
    all_connections: List[str],
    node_definitions: Dict[str, str],
    styles: Dict[str, str],
    colors: Dict[str, str],
    header_lines: List[str],
    output_dir: Path
) -> None:
    """
    Export each subgraph as a separate Mermaid diagram file.
    
    Args:
        namespace_groups: All namespace groups
        all_connections: All connections in the original diagram
        node_definitions: Mapping of node_id to node_content (with links if present)
        styles: Style definitions for nodes
        colors: Fill colors for nodes
        header_lines: Header lines from the original diagram
        output_dir: Directory to write output files
    """
    print("\nExporting individual subgraph diagrams...")
    
    for namespace in sorted(namespace_groups.keys()):
        # Generate filename from namespace (e.g., /planning -> planning.mermaid.html)
        filename = namespace.strip('/').replace('/', '_') + '.mermaid.html'
        if not filename.startswith('/'):
            filename = filename if filename else 'root.mermaid.html'
        
        output_file = output_dir / filename
        
        # Generate the diagram
        mermaid_content = generate_individual_subgraph_mermaid(
            namespace,
            namespace_groups,
            all_connections,
            node_definitions,
            styles,
            colors,
            header_lines
        )
        
        # Write to file as HTML
        with open(output_file, 'w') as f:
            f.write('<!doctype html>\n')
            f.write('<html lang="en">\n')
            f.write('  <head>\n')
            f.write('    <link rel="icon" type="image/x-icon" href="https://mermaid.js.org/favicon.ico">\n')
            f.write('    <meta charset="utf-8">\n')
            f.write(f'    <title>ROS Node Graph - {namespace}</title>\n')
            f.write('    <style>\n')
            f.write('    pre.mermaid {\n')
            f.write('      font-family: "Fira Mono", "Roboto Mono", "Source Code Pro", monospace;\n')
            f.write('    }\n')
            f.write('    </style>\n')
            f.write('  </head>\n')
            f.write('  <body>\n')
            f.write('    <pre class="mermaid">\n')
            f.write(mermaid_content)
            f.write('\n    </pre>\n')
            f.write('    <script type="module">\n')
            f.write('      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";\n')
            f.write('      mermaid.initialize({ startOnLoad: true, flowchart: { useMaxWidth: false, htmlLabels: true } });\n')
            f.write('    </script>\n')
            f.write('  </body>\n')
            f.write('</html>\n')
        
        print(f"  Created: {output_file.name}")
    
    print(f"\nExported {len(namespace_groups)} individual subgraph diagrams.")


def main():
    """Main function to process the Mermaid diagram."""
    parser = argparse.ArgumentParser(
        description="Split a large Mermaid diagram into subgraphs based on node namespaces."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Input Mermaid file (HTML or Markdown format, default: ros_graph_linked.mermaid.html)",
        default="ros_graph_linked.mermaid.html"
    )
    parser.add_argument(
        "-d", "--output-dir",
        type=str,
        help="Output directory for individual subgraph HTML files (default: current directory)",
        default="."
    )
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    
    # Determine input file
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = script_dir / input_path
    input_file = input_path
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return 1
    
    # Determine output directory
    output_dir_path = Path(args.output_dir)
    if not output_dir_path.is_absolute():
        output_dir_path = script_dir / output_dir_path
    output_dir = output_dir_path
    
    print(f"Reading Mermaid diagram from: {input_file}")
    
    # Parse the input file
    header_lines, node_definitions, connections = parse_mermaid_file(str(input_file))
    styles = get_node_styles(str(input_file))
    colors = get_node_colors(str(input_file))
    
    print(f"Found {len(node_definitions)} nodes and {len(connections)} connections")
    print(f"Extracted {len(colors)} node colors")
    
    # Group nodes by namespace
    namespace_groups = group_nodes_by_namespace(node_definitions)
    print(f"\nNamespace groups found:")
    for ns, nodes in sorted(namespace_groups.items()):
        print(f"  {ns}: {len(nodes)} nodes")
    
    # Classify connections
    external_connections, internal_connections = classify_connections(connections, namespace_groups)
    print(f"\nConnections: {len(external_connections)} external, "
          f"{sum(len(v) for v in internal_connections.values())} internal")
    
    # Export individual subgraph diagrams
    export_individual_subgraphs(
        namespace_groups,
        connections,
        node_definitions,
        styles,
        colors,
        header_lines,
        output_dir
    )
    
    print("\nYou can view the diagrams by opening the HTML files in a web browser.")
    
    return 0


if __name__ == '__main__':
    exit(main())
