#!/bin/bash
# Script to generate node-centric pages and split diagrams into subgraphs
# Usage: ./generate_node_page.sh <input_mermaid_file> [output_directory]

set -e  # Exit on error

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    echo "Usage: $0 <input_mermaid_file> [output_directory]"
    echo ""
    echo "Arguments:"
    echo "  input_mermaid_file   Path to the input Mermaid HTML file (required)"
    echo "  output_directory     Output directory path (optional, defaults to current directory)"
    exit 1
fi

# Set output directory (default to current directory if not specified)
if [ -n "$2" ]; then
    if [[ "$2" = /* ]]; then
        # Already absolute path
        OUTPUT_DIR="$2"
    else
        # Convert relative path to absolute
        OUTPUT_DIR="$(cd "$(dirname "$2")" 2>/dev/null && pwd)/$(basename "$2")"
    fi
    # Create output directory if it doesn't exist
    mkdir -p "$OUTPUT_DIR"
else
    OUTPUT_DIR="$(pwd)"
fi

# Output files in output directory
LINKED_OUTPUT="$OUTPUT_DIR/ros_graph_linked.mermaid.html"
NODES_DIR="$OUTPUT_DIR/nodes"
SUBGRAPH_DIR="$OUTPUT_DIR"

# Print configuration
echo "======================================================================"
echo "ROS Node Graph Generation Pipeline"
echo "======================================================================"
echo "Input file:             $INPUT_FILE"
echo "Output directory:       $OUTPUT_DIR"
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
