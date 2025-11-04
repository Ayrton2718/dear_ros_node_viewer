#!/usr/bin/env python3
"""
Generate Mermaid graph HTML for each node from the architecture diagram.
Creates individual node-centric graphs and a main diagram with clickable links.
Input must be an HTML file containing a Mermaid diagram.
"""

import re
import os
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set


class MermaidGraphGenerator:
    def __init__(self, input_file: str):
        self.input_file = input_file
        self.nodes: Dict[str, Dict[str, str]] = {}  # node_id -> {name, color}
        self.connections: List[Tuple[str, str, str]] = []  # (from_id, to_id, topics)
        self.config_lines: List[str] = []
        self.graph_type = "graph TD"
        
    def parse_mermaid_file(self):
        """Parse the Mermaid markdown file to extract nodes and connections."""
        print(f"Reading Mermaid diagram from: {self.input_file}")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # try to extract from HTML <pre class="mermaid"> tag
        mermaid_match = re.search(r'<pre class="mermaid">\s*(.*?)\s*</pre>', content, re.DOTALL)
        
        if not mermaid_match:
            raise ValueError("No mermaid code block found in the file (tried both markdown and HTML formats)")
        
        mermaid_code = mermaid_match.group(1)
        lines = mermaid_code.strip().split('\n')
        
        # Parse config section
        in_config = False
        for line in lines:
            line = line.strip()
            if line.startswith('---'):
                in_config = not in_config
                continue
            if in_config or line.startswith('config:'):
                self.config_lines.append(line)
                continue
            
            # Parse graph type
            if line.startswith('graph '):
                self.graph_type = line
                continue
            
            # Parse node definitions
            node_match = re.match(r'^([A-Z]+)\(\[(.+?)\]\)$', line)
            if node_match:
                node_id = node_match.group(1)
                node_name = node_match.group(2)
                self.nodes[node_id] = {'name': node_name, 'color': '#808080'}
                continue
            
            # Parse style definitions
            style_match = re.match(r'^style ([A-Z]+) fill:(#[0-9a-fA-F]+), color:(#[0-9a-fA-F]+)$', line)
            if style_match:
                node_id = style_match.group(1)
                fill_color = style_match.group(2)
                if node_id in self.nodes:
                    self.nodes[node_id]['color'] = fill_color
                continue
            
            # Parse connections
            connection_match = re.match(r'^([A-Z]+) -->(?:\|(.+?)\|)? ([A-Z]+)$', line)
            if connection_match:
                from_id = connection_match.group(1)
                topics = connection_match.group(2) or ""
                to_id = connection_match.group(3)
                self.connections.append((from_id, to_id, topics))
                continue
        
        print(f"Found {len(self.nodes)} nodes and {len(self.connections)} connections")
    
    def get_node_connections(self, node_id: str) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Get all incoming and outgoing connections for a node.
        
        Returns:
            (incoming, outgoing) where each is a list of (connected_node_id, topics)
        """
        incoming = []
        outgoing = []
        
        for from_id, to_id, topics in self.connections:
            if to_id == node_id:
                incoming.append((from_id, topics))
            elif from_id == node_id:
                outgoing.append((to_id, topics))
        
        return incoming, outgoing
    
    def generate_node_graph(self, node_id: str, add_links: bool = False) -> str:
        """Generate a Mermaid graph centered on a specific node.
        
        Args:
            node_id: The ID of the central node
            add_links: If True, add clickable links to connected nodes
        """
        if node_id not in self.nodes:
            return ""
        
        node_info = self.nodes[node_id]
        incoming, outgoing = self.get_node_connections(node_id)
        
        # Build the mermaid graph
        lines = []
        lines.append("```mermaid")
        lines.append("---")
        lines.append("config:")
        lines.append("  layout: dagre")
        lines.append("  look: neo")
        lines.append("  theme: neutral")
        lines.append("---")
        lines.append(self.graph_type)
        
        # Define the central node (no link since we're already on this page)
        lines.append(f"{node_id}([{node_info['name']}])")
        lines.append(f"style {node_id} fill:{node_info['color']}, color:#ffffff, stroke:#000000, stroke-width:4px")
        
        # Collect all connected nodes
        connected_nodes = set()
        
        # Define incoming nodes with optional links
        for from_id, _ in incoming:
            if from_id in self.nodes:
                connected_nodes.add(from_id)
                from_info = self.nodes[from_id]
                if add_links:
                    safe_name = from_info['name'].replace('/', '_').strip('_')
                    lines.append(f'{from_id}([<a class="node-link" href="{safe_name}.html">{from_info["name"]}</a>])')
                else:
                    lines.append(f"{from_id}([{from_info['name']}])")
                lines.append(f"style {from_id} fill:{from_info['color']}, color:#ffffff")
        
        # Define outgoing nodes with optional links
        for to_id, _ in outgoing:
            if to_id in self.nodes:
                connected_nodes.add(to_id)
                to_info = self.nodes[to_id]
                if add_links:
                    safe_name = to_info['name'].replace('/', '_').strip('_')
                    lines.append(f'{to_id}([<a class="node-link" href="{safe_name}.html">{to_info["name"]}</a>])')
                else:
                    lines.append(f"{to_id}([{to_info['name']}])")
                lines.append(f"style {to_id} fill:{to_info['color']}, color:#ffffff")
        
        # Add connections
        for from_id, topics in incoming:
            if from_id in self.nodes:
                if topics:
                    lines.append(f"{from_id} -->|{topics}| {node_id}")
                else:
                    lines.append(f"{from_id} --> {node_id}")
        
        for to_id, topics in outgoing:
            if to_id in self.nodes:
                if topics:
                    lines.append(f"{node_id} -->|{topics}| {to_id}")
                else:
                    lines.append(f"{node_id} --> {to_id}")
        
        lines.append("```")
        
        return '\n'.join(lines)
    
    def generate_node_html(self, node_id: str, output_dir: Path) -> str:
        """Generate an HTML file for a specific node."""
        if node_id not in self.nodes:
            return ""
        
        node_info = self.nodes[node_id]
        node_name = node_info['name']
        
        # Generate the mermaid graph with clickable links
        mermaid_graph = self.generate_node_graph(node_id, add_links=True)
        
        # Get connection statistics
        incoming, outgoing = self.get_node_connections(node_id)
        
        # Create HTML content
        html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <link rel="icon" type="image/x-icon" href="https://mermaid.js.org/favicon.ico">
    <meta charset="utf-8">
    <title>Node: {node_name}</title>
    <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
      background-color: #f5f5f5;
    }}
    .header {{
      background-color: {node_info['color']};
      color: #ffffff;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 20px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 24px;
    }}
    .stats {{
      display: flex;
      gap: 20px;
      margin-bottom: 20px;
    }}
    .stat-box {{
      background-color: white;
      padding: 15px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      flex: 1;
    }}
    .stat-box h3 {{
      margin: 0 0 10px 0;
      font-size: 14px;
      color: #666;
    }}
    .stat-box .number {{
      font-size: 32px;
      font-weight: bold;
      color: #333;
    }}
    .back-link {{
      display: inline-block;
      margin-bottom: 20px;
      padding: 10px 20px;
      background-color: #007bff;
      color: white;
      text-decoration: none;
      border-radius: 5px;
    }}
    .back-link:hover {{
      background-color: #0056b3;
    }}
    .graph-container {{
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    pre.mermaid {{
      font-family: "Fira Mono", "Roboto Mono", "Source Code Pro", monospace;
    }}
    .node-link {{
      text-decoration: none;
      color: inherit;
      font-weight: bold;
    }}
    .node-link:hover {{
      text-decoration: underline;
      opacity: 0.8;
    }}
    </style>
  </head>
  <body>
    <a href="../ros_graph_linked.mermaid.html" class="back-link">← Back to Main Graph</a>
    
    <div class="header">
      <h1>Node: {node_name}</h1>
    </div>
    
    <div class="stats">
      <div class="stat-box">
        <h3>Subscribers</h3>
        <div class="number">{len(incoming)}</div>
      </div>
      <div class="stat-box">
        <h3>Publishers</h3>
        <div class="number">{len(outgoing)}</div>
      </div>
      <div class="stat-box">
        <h3>Total Connections</h3>
        <div class="number">{len(incoming) + len(outgoing)}</div>
      </div>
    </div>
    
    <div class="graph-container">
      <h2>Node Connection Graph</h2>
      <pre class="mermaid">
{mermaid_graph.replace('```mermaid', '').replace('```', '').strip()}
      </pre>
    </div>
    
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, flowchart: {{ useMaxWidth: false, htmlLabels: true }} }});
    </script>
  </body>
</html>
"""
        
        # Save to file
        safe_name = node_name.replace('/', '_').strip('_')
        output_file = output_dir / f"{safe_name}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(output_file)
    
    def generate_all_node_htmls(self, output_dir: Path):
        """Generate HTML files for all nodes."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nGenerating individual node graphs in: {output_dir}")
        
        generated = []
        for node_id in sorted(self.nodes.keys()):
            output_file = self.generate_node_html(node_id, output_dir)
            if output_file:
                generated.append(output_file)
                print(f"  Created: {Path(output_file).name}")
        
        print(f"\nGenerated {len(generated)} node HTML files")
        return generated
    
    def generate_linked_main_graph(self, output_file: Path, nodes_dir: str = "nodes"):
        """Generate the main graph with clickable links to individual node pages."""
        print(f"\nGenerating linked main graph: {output_file}")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to extract mermaid code from markdown code block first
        mermaid_match = re.search(r'```mermaid\n(.*?)```', content, re.DOTALL)
        
        # If not found, try to extract from HTML <pre class="mermaid"> tag
        if not mermaid_match:
            mermaid_match = re.search(r'<pre class="mermaid">\s*(.*?)\s*</pre>', content, re.DOTALL)
        
        if not mermaid_match:
            raise ValueError("No mermaid code block found in the file (tried both markdown and HTML formats)")
        
        mermaid_code = mermaid_match.group(1)
        
        # Replace node definitions with linked versions
        modified_code = mermaid_code
        for node_id, node_info in self.nodes.items():
            node_name = node_info['name']
            safe_name = node_name.replace('/', '_').strip('_')
            link_path = f"{nodes_dir}/{safe_name}.html"
            
            # Original pattern
            original = f"{node_id}([{node_name}])"
            # Linked version
            linked = f'{node_id}([<a class="internal-link" href="{link_path}">{node_name}</a>])'
            
            modified_code = modified_code.replace(original, linked)
        
        # Create HTML with the modified graph
        html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <link rel="icon" type="image/x-icon" href="https://mermaid.js.org/favicon.ico">
    <meta charset="utf-8">
    <title>ROS Node Graph (Interactive)</title>
    <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
      background-color: #f5f5f5;
    }}
    .header {{
      background-color: #333;
      color: white;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 20px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 28px;
    }}
    .header p {{
      margin: 10px 0 0 0;
      opacity: 0.9;
    }}
    .graph-container {{
      background-color: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    pre.mermaid {{
      font-family: "Fira Mono", "Roboto Mono", "Source Code Pro", monospace;
    }}
    .internal-link {{
      text-decoration: none;
      color: inherit;
      font-weight: bold;
    }}
    .internal-link:hover {{
      text-decoration: underline;
    }}
    </style>
  </head>
  <body>
    <div class="header">
      <h1>ROS Node Graph (Interactive)</h1>
      <p>Click on any node to view its detailed connections and information</p>
    </div>
    
    <div class="graph-container">
      <pre class="mermaid">
{modified_code.strip()}
      </pre>
    </div>
    
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{ startOnLoad: true, flowchart: {{ useMaxWidth: false, htmlLabels: true }} }});
    </script>
  </body>
</html>
"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Linked main graph saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Mermaid graph HTML for each node from the architecture diagram."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Input Mermaid HTML file",
        default=None
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file for the linked main graph (default: ros_graph_linked.mermaid.html)",
        default="ros_graph_linked.mermaid.html"
    )
    parser.add_argument(
        "-d", "--output-dir",
        type=str,
        help="Output directory for individual node HTML files (default: nodes)",
        default="nodes"
    )
    
    args = parser.parse_args()
    
    # Configuration
    script_dir = Path(__file__).parent
    
    # Determine input file
    if args.input:
        input_file = Path(args.input)
        if not input_file.is_absolute():
            input_file = script_dir / input_file
    else:
        print("No input file specified, using default 'ros_graph.mermaid.html'")
        return 1
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        print("\nPlease specify an input HTML file with -i/--input option")
        return 1
    
    # Verify it's an HTML file
    if not input_file.suffix == '.html':
        print(f"Error: Input file must be an HTML file, got: {input_file.suffix}")
        return 1
    
    # Output configuration
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = script_dir / output_path
    
    output_dir_path = Path(args.output_dir)
    if not output_dir_path.is_absolute():
        output_dir_path = script_dir / output_dir_path
    
    nodes_output_dir = output_dir_path
    linked_main_graph = output_path
    
    # Generate graphs
    generator = MermaidGraphGenerator(str(input_file))
    generator.parse_mermaid_file()
    generator.generate_all_node_htmls(nodes_output_dir)
    generator.generate_linked_main_graph(linked_main_graph, nodes_dir="nodes")
    
    print("\n" + "="*70)
    print("Generation complete!")
    print("="*70)
    print(f"\nMain interactive graph: {linked_main_graph}")
    print(f"Individual node graphs: {nodes_output_dir}/")
    print("\nYou can view the interactive graph by opening the HTML file in a web browser.")
    print("Click on any node in the main graph to view its detailed connections.")
    
    return 0


if __name__ == "__main__":
    exit(main())
