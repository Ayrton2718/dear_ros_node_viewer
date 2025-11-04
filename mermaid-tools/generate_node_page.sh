#!/bin/bash
# Script to generate node-centric pages and split diagrams into subgraphs
# Usage: ./generate_node_page.sh [input_mermaid_file]

set -e  # Exit on error

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$(pwd)"

# Convert INPUT_FILE to absolute path
if [ -n "$1" ]; then
    if [[ "$1" = /* ]]; then
        # Already absolute path
        INPUT_FILE="$1"
    else
        # Convert relative path to absolute
        INPUT_FILE="$(cd "$(dirname "$1")" 2>/dev/null && pwd)/$(basename "$1")"
    fi
else
    echo "No input file specified, using default 'ros_graph.mermaid.html'"
    exit 1
fi

# Output files in current directory
LINKED_OUTPUT="$CURRENT_DIR/ros_graph_linked.mermaid.html"
NODES_DIR="$CURRENT_DIR/nodes"
SUBGRAPH_DIR="$CURRENT_DIR"

# Print configuration
echo "======================================================================"
echo "ROS Node Graph Generation Pipeline"
echo "======================================================================"
echo "Input file:             $INPUT_FILE"
echo "Linked graph output:    $LINKED_OUTPUT"
echo "Individual nodes dir:   $NODES_DIR"
echo "Subgraph files dir:     $SUBGRAPH_DIR"
echo "======================================================================"
echo ""

# Step 1: Generate node-centric graphs with clickable links
echo "Step 1: Generating node-centric graphs..."
echo "----------------------------------------------------------------------"
python3 "$SCRIPT_DIR/generate_node_centric.py" \
    -i "$INPUT_FILE" \
    -o "$LINKED_OUTPUT" \
    -d "$NODES_DIR"

if [ $? -ne 0 ]; then
    echo "Error: Failed to generate node-centric graphs"
    exit 1
fi

echo ""
echo "Step 1 complete!"
echo ""

# Step 2: Split the linked graph into subgraphs by namespace
echo "Step 2: Splitting diagram into subgraphs..."
echo "----------------------------------------------------------------------"
python3 "$SCRIPT_DIR/split_mermaid_diagram.py" \
    -i "$LINKED_OUTPUT" \
    -d "$SUBGRAPH_DIR"

if [ $? -ne 0 ]; then
    echo "Error: Failed to split diagram into subgraphs"
    exit 1
fi

echo ""
echo "Step 2 complete!"
echo ""

# Summary
echo "======================================================================"
echo "Generation Pipeline Complete!"
echo "======================================================================"
echo ""
echo "Generated files:"
echo "  1. Main interactive graph:   $LINKED_OUTPUT"
echo "  2. Individual node pages:    $NODES_DIR/"
echo "  3. Individual subgraphs:     $SUBGRAPH_DIR/*.mermaid.html"
echo ""
echo "You can view the diagrams by opening the HTML files in a web browser."
echo "======================================================================"
