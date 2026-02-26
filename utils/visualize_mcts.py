import json
import os
import argparse
from graphviz import Digraph
import textwrap

def split_text(text, width=40):
    text = str(text)
    return textwrap.fill(text, width=width)

def visualize_mcts_tree(tree_data, output_path, tree_index, problem_index):
    """
    Visualizes a single MCTS tree from the JSON data (Standard MCTS format).
    """
    g = Digraph(f'MCTS_Tree_{problem_index}_{tree_index}', format='png')
    g.attr(rankdir='TB')
    g.attr('node', shape='box', style='filled', color='lightblue', fontname='Helvetica')

    fathers = tree_data.get('fathers', {})
    childs = tree_data.get('childs', {})
    to_explore_reward = tree_data.get('to_explore_reward', {})
    to_explore = tree_data.get('to_explore', [])
    
    root_node = None
    all_nodes = set()
    
    if fathers:
        for node, father in fathers.items():
            all_nodes.add(node)
            if father is None:
                root_node = node
            else:
                all_nodes.add(father)
    else:
        if to_explore:
            root_node = to_explore[0]
            all_nodes.update(to_explore)

    if not root_node:
        # Fallback for empty tree
        return

    for node_content in all_nodes:
        rewards = to_explore_reward.get(node_content, [])
        avg_reward = sum(rewards)/len(rewards) if rewards else 0.0
        
        label = f"Reward: {avg_reward:.2f}\n" 
        label += f"Visits: {len(rewards)}\n"
        label += "-"*10 + "\n"
        truncated_content = split_text(str(node_content))
        if len(truncated_content) > 300:
             truncated_content = truncated_content[:300] + "..."
        label += truncated_content

        fillcolor = 'white'
        if node_content == root_node:
            fillcolor = 'lightgrey'
        elif avg_reward > 90:
            fillcolor = 'lightgreen'
        
        g.node(str(hash(node_content)), label=label, fillcolor=fillcolor)

    if childs:
        for parent, children_list in childs.items():
            parent_id = str(hash(parent))
            for child in children_list:
                child_id = str(hash(child))
                g.edge(parent_id, child_id)
    elif fathers:
         for child, parent in fathers.items():
            if parent:
                g.edge(str(hash(parent)), str(hash(child)))

    full_output_path = os.path.join(output_path, f'tree_{problem_index}_{tree_index}')
    g.render(full_output_path, view=False)
    print(f"Generated visualization: {full_output_path}.png")


def visualize_game24_tree(item, output_path, problem_index):
    """
    Visualizes a Game24 tree from the 'steps' based log.
    Structure is layered:
      Step 0: root 'x' expands to 'new_ys'
      Step 1: selected nodes from Step 0 expand to their 'new_ys'
    """
    g = Digraph(f'Game24_Tree_{problem_index}', format='png')
    g.attr(rankdir='TB')
    g.attr('node', shape='box', style='filled', color='lightblue', fontname='Helvetica')

    steps = item.get('steps', [])
    if not steps:
        return

    # Game24 typically starts with an initial input 'x'
    initial_x = steps[0].get('x', 'root')
    root_id = "root_0"
    g.node(root_id, label=f"Start: {initial_x}", fillcolor='lightgrey')
    
    # We need to track IDs of nodes in the previous layer to connect them to the next
    # In Step 0: 'ys' is just [""] (or similar). 'new_ys' is a list of proposed next steps.
    # The 'root' connects to all in 'new_ys'.
    
    # But wait, Step 1 has 'ys' which matches 'select_new_ys' from Step 0.
    # And 'new_ys' in Step 1 is a LIST OF LISTS, corresponding to each element in 'ys'.
    
    # Layer 0 ID mapping:  0 -> root_id
    
    # Let's generalize:
    # Layer K IDs: A list of node IDs that were "selected" and passed to step K+1.
    
    # For Step 0:
    # "Selected" nodes are effectively the single root (since ys=[""]). 
    # Wait, Step 0 'select_new_ys' are the children of Root that survived.
    # But 'new_ys' contains ALL generated children.
    
    # Let's map unique strings to IDs to avoid duplication if states loop (unlikely in Game24 but possible).
    # Actually, tree visualizer usually wants unique nodes per path or just unique values.
    # Let's use unique values.
    
    node_registry = {} # content -> id
    
    def get_id(content):
        content = content.strip()
        if content not in node_registry:
            node_registry[content] = f"node_{len(node_registry)}"
            
            # Label
            label = split_text(content)
            g.node(node_registry[content], label=label, fillcolor='white')
        return node_registry[content]

    # Initialize with root
    # Step 0 'x' is the root content
    root_content = initial_x
    root_node_id = get_id(root_content)
    g.node(root_node_id, fillcolor='lightgrey')

    # Current layer parents: initially just [root_content]
    # But looking at Step 0 structure:
    # 'ys' = [""] ... this is confusing. 
    # Actually checking `run.py` for Game24 might help, but let's infer from JSON.
    # Step 0 'new_ys' is a flat list of strings. These are children of Root.
    # Step 0 'values' corresponds to 'new_ys'.
    # Step 0 'select_new_ys' is a subset of 'new_ys' that proceeds to next step.
    
    # So:
    # Root -> all 'new_ys' in Step 0.
    # Highlighting those in 'select_new_ys'.
    
    # Step 1:
    # 'ys' = Step 0 'select_new_ys'.
    # 'new_ys' = List of lists. `new_ys[i]` are children of `ys[i]`.
    
    # Reconstructing:
    
    # 1. Draw Root.
    # 2. Iterate steps.
    
    previous_layer_selected_nodes = [root_content] # starts with root
    
    for i, step in enumerate(steps):
        # 'ys' in step i are the parents for this expansion (except step 0 where ys=[""])
        # 'new_ys' is a list of list of children (except step 0 where it is flat list)
        
        current_ys = step.get('ys', [])
        current_new_ys = step.get('new_ys', [])
        
        # Normalize Step 0 to match others
        if i == 0:
             # In step 0, 'ys' is dummy. Root is the parent.
             # 'new_ys' is flat list. Wrap it in a list to match list-of-lists structure logic if we treat root as the single parent.
             current_ys = [root_content]
             current_new_ys = [current_new_ys] # Wrap flat list into list of lists (one parent)
        
        # 'select_new_ys' are the nodes that will become parents in next step
        next_selected = step.get('select_new_ys', [])
        
        if len(current_ys) != len(current_new_ys):
            print(f"Warning: Step {i} length mismatch ys vs new_ys")
            continue

        for parent_idx, parent_content in enumerate(current_ys):
            parent_id = get_id(parent_content)
            
            children = current_new_ys[parent_idx]
            for child_content in children:
                child_id = get_id(child_content)
                g.edge(parent_id, child_id)
                
                # Highlight if selected
                if child_content in next_selected:
                    g.node(child_id, color='green', penwidth='2.0')

    full_output_path = os.path.join(output_path, f'game24_tree_{problem_index}')
    g.render(full_output_path, view=False)
    print(f"Generated visualization: {full_output_path}.png")


def main():
    parser = argparse.ArgumentParser(description='Visualize Trees from Forest-of-Thought JSON output')
    parser.add_argument('json_file', type=str, help='Path to the JSON output file')
    parser.add_argument('--output_dir', type=str, default='visualizations', help='Directory to save visualizations')
    parser.add_argument('--max_trees', type=int, default=5, help='Maximum number of trees to visualize per file')

    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    try:
        with open(args.json_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return

    # Detect Game24 format
    # Game24 log is a list of objects, each having "steps", "idx"
    is_game24 = False
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if 'steps' in first and 'x' in first['steps'][0]:
            is_game24 = True

    if is_game24:
        print("Detected Game24 log format.")
        count = 0
        for item in data:
            if count >= args.max_trees:
                break
            visualize_game24_tree(item, args.output_dir, item.get('idx', count))
            count += 1
    else:
        # Assume Standard MCTS format (nested 'data' with 'fathers')
        if isinstance(data, list):
            count = 0
            for item in data:
                if count >= args.max_trees:
                    break
                problem_index = item.get('index', 'unknown')
                inner_data = item.get('data', {})
                if 'fathers' in inner_data:
                    print(f"Visualizing problem {problem_index}...")
                    visualize_mcts_tree(inner_data, args.output_dir, "last_tree", problem_index)
                    count += 1
        elif isinstance(data, dict):
             visualize_mcts_tree(data, args.output_dir, "single", "0")

if __name__ == '__main__':
    main()
