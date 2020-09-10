import datetime
import distutils.dir_util
import filecmp
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile

import graphviz


class WitNotFoundError(Exception):
    pass


def init():
    sub_folders = ['images', 'staging_area']
    for subfolder in sub_folders:
        try:
            os.makedirs(os.path.join(os.getcwd(), '.wit', subfolder))
        except FileExistsError:
            print("The directory already exists.")
            return False
    
    with open(os.getcwd() + '\\.wit\\activated.txt', 'w') as file:
        file.write('master')
    
    print("Init action was successful")


def find_wit(full_path, dest):
    if '.wit' in os.listdir(full_path):
        # print(f'.wit is in {full_path}')
        dest = full_path + '\\' + dest
        return dest, full_path
    
    for parent in Path(full_path).parents:
        if '.wit' in os.listdir(parent):
            dest = str(parent) + "\\" + dest
            # print(f'.wit is in {str(parent)}')
            return dest, str(parent)
    
    raise WitNotFoundError("Couldn't find .wit anywhere.")


def add(f_name):
    dest = '.wit\\staging_area'

    if os.path.exists(f_name):
        print(f"Path {f_name} exists")
        dest, base_path = find_wit(os.getcwd(), dest)

        if base_path not in f_name:
            dest += '\\' + os.getcwd().replace(base_path, '')

        if os.path.isdir(f_name):
            dest += '\\' + os.path.dirname(f_name.replace(base_path, '') + '\\' + os.path.basename(f_name))
            if not os.path.exists(dest):
                os.makedirs(dest)
            distutils.dir_util.copy_tree(f_name, dest)
        elif os.path.isfile(f_name):
            dest += '\\' + os.path.dirname(f_name.replace(base_path, ''))
            if not os.path.exists(dest):
                os.makedirs(dest)
            shutil.copy(f_name, dest)

        print(f"{f_name} has been coppied to {dest}")
        return True

    else:
        print(f"Path {f_name} does not exist")
    return False


def generate_commit_id():
    return ''.join(random.choice('1234567890abcdef') for _ in range(40))


def get_diff_files(dcmp, differ_dict, relpath):
    for file in dcmp.diff_files:
        if dcmp.right == relpath:
            file_path = file
        else:
            file_path = dcmp.right.replace(relpath + "\\", '') + "\\" + file
        differ_dict['common'].append(file_path)
        # print(f"{name} has been modified.")
    
    for file in dcmp.right_only:
        if dcmp.right == relpath:
            file_path = file
        else:
            file_path = dcmp.right.replace(relpath + "\\", '') + "\\" + file
        differ_dict['to_be_added'].append(file_path)
        # print(f"{name} has been modified.")

    for sub_dcmp in dcmp.subdirs.values():
        get_diff_files(sub_dcmp, differ_dict, relpath)
    
    return differ_dict


def check_if_can_commit(base_path, parent):
    if parent is not None:
        head_commit = base_path + "\\.wit\\images\\" + parent
        if os.path.exists(head_commit):
            dcmp = filecmp.dircmp(head_commit, base_path + "\\.wit\\staging_area")
            differ_dict = get_diff_files(dcmp, {'common': [], 'to_be_added': []}, base_path + "\\.wit\\staging_area")
            if differ_dict['common'] == [] and differ_dict['to_be_added'] == []:
                return False
            return True
        return True
    return True


def get_commit_id(references, key):
    key += '='
    if os.path.exists(references):
        with open(references, 'r') as file:
            file = file.readlines()
        for line in file:
            if line.startswith(key):
                split_line = line.split('=')
                return split_line[1].strip('\n')
    return None


def get_active_branch():
    active_path, _ = find_wit(os.getcwd(), '.wit\\activated.txt')
    if os.path.exists(active_path):
        with open(active_path, 'r') as file:
            return file.readline().strip('\n')
    return None


def update_references(references, commit_id, checkout=False):
    if not os.path.exists(references):
        if not checkout:
            with open(references, 'w') as file:
                file.write(f'HEAD={commit_id}\n')
                file.write(f'master={commit_id}\n')
            return True
        print("There are no other references documented. Checkout failed.")
        return False
        
    head = get_commit_id(references, 'HEAD')
    master = get_commit_id(references, 'master')
    active_branch = get_active_branch()

    if active_branch:
        active_branch_commit_id = get_commit_id(references, active_branch)

    updated_head = False
    updated_master = False

    with open(references, 'r+') as file:
        file_lines = file.readlines()
        for index, line in enumerate(file_lines):
            if line.startswith('HEAD='):
                file_lines[index] = f'HEAD={commit_id}\n'
                updated_head = True

            elif line.startswith('master='):
                if not checkout and head == master and active_branch == 'master':
                    file_lines[index] = f'master={commit_id}\n'
                updated_master = True
            
            if active_branch:
                if line.startswith(f'{active_branch}=') and head == active_branch_commit_id:
                    file_lines[index] = f'{active_branch}={commit_id}\n'

        file.seek(0)
        file.truncate()

        if updated_head and updated_master:
            file.writelines(file_lines)
            return True
        
        if not checkout:
            file_lines.insert(0, f'HEAD={commit_id}\n')
            file_lines.append(f'master={commit_id}\n')
            file.writelines(file_lines)
            return True
        return False


def commit(message, branch=None):
    dest, base_path = find_wit(os.getcwd(), '.wit\\images')
    if base_path:
        commit_id = generate_commit_id()
        references = base_path + "\\.wit\\references.txt"
        parent = None

        while os.path.exists(dest + "\\" + commit_id):
            commit_id = generate_commit_id()
        commit_dest = dest + "\\" + commit_id

        parent = get_commit_id(references, 'HEAD')
        if parent:
            print(f"(HEAD={parent})")
        if check_if_can_commit(base_path, parent):
            if not os.path.exists(commit_dest):
                os.makedirs(commit_dest)
            
            if branch:
                if branch != parent:
                    parent += f',{branch}'
            
            meta_dict = {'parent': parent, 'date': datetime.datetime.now(), 'message': message}
            with open(commit_dest + '.txt', 'w') as file:
                for key, value in meta_dict.items():
                    file.write(f'{key}={value}\n')
            
            distutils.dir_util.copy_tree(base_path + '\\.wit\\staging_area', commit_dest)
            if update_references(references, commit_id):
                print(f"(*HEAD={commit_id})")

        else:
            print("No changes were made to directory. Commit failed.")


def get_status(dest, base_path):
    if base_path:
        references = base_path + "\\.wit\\references.txt"
        parent = get_commit_id(references, 'HEAD')
        
        head_commit = dest + "\\" + parent
        if os.path.exists(head_commit):
            dcmp = filecmp.dircmp(head_commit, base_path + "\\.wit\\staging_area")
            differ_dict1 = get_diff_files(dcmp, {'common': [], 'to_be_added': []}, base_path + "\\.wit\\staging_area")

            # print("Changes to be committed:")
            # print(differ_dict1['to_be_added'])

            dcmp = filecmp.dircmp(base_path + "\\.wit\\staging_area", base_path)
            differ_dict2 = get_diff_files(dcmp, {'common': [], 'to_be_added': []}, base_path)
            differ_dict2['to_be_added'].remove(".wit")

            # print("Changes not staged for commit:")
            # print(differ_dict2['common'])
            # print("Untracked files:")
            # print(differ_dict2['to_be_added'])

            return [parent, differ_dict1['to_be_added'], differ_dict2['common'], differ_dict2['to_be_added']]
        return False
    return False


def status():
    dest, base_path = find_wit(os.getcwd(), '.wit\\images')
    status = get_status(dest, base_path)
    if status:
        print(status[0])
        print("Changes to be commited:")
        print(status[1])
        print("Changes not staged for commit:")
        print(status[2])
        print("Untracked files:")
        print(status[3])


def checkout(commit_id):
    images, base_path = find_wit(os.getcwd(), '.wit\\images')
    if base_path:
        references = base_path + "\\.wit\\references.txt"
        original_commit_insert = (commit_id + '.')[:-1]

        status = get_status(images, base_path)
        if status:
            if len(status[1]) > 0 or len(status[2]) > 0:
                print("Checkout failed.")
                return False
        
        if commit_id == 'master':
            commit_id = get_commit_id(references, 'master')
        
        if not os.path.exists(images + "\\" + commit_id):
            branch = get_commit_id(references, commit_id)
            if os.path.exists(images + "\\" + str(branch)):
                commit_id = branch
        
        if os.path.exists(images + "\\" + commit_id):
            distutils.dir_util.copy_tree(images + "\\" + commit_id, base_path)
            with open(base_path + "\\.wit\\activated.txt", 'w') as file:
                if original_commit_insert != commit_id:
                    file.write(f"{original_commit_insert}")
                else:
                    file.write('')
            update_references(references, commit_id, checkout=True)
            print("Checkout was successful.")
            return True

        print("Checkout wasn't successful.")
        return False


def make_graph(parents):
    d = graphviz.Digraph(name='Parents', comment='Parents', format='png')
    
    for parent in parents.keys():
        d.node(str(parent), str(parent))
    
    for key, value in parents.items():
        if ',' not in value:
            d.edge(str(key), str(value))
        else:
            sep_value = value.split(',')
            d.edge(str(key), str(sep_value[0]))
            d.edge(str(key), str(sep_value[1]))
    
    d.graph_attr['rankdir'] = 'RL'
    d.node_attr.update({'shape': 'circle',
                        'style': 'filled',
                        'color': 'lightblue2',
                        'fontsize': '12'})
    
    # d.view(tempfile.mktemp())
    d.view(tempfile.mkstemp()[1])


def get_ref_dict(references):
    ref_dict = {}

    if os.path.exists(references):
        with open(references, 'r') as file:
            f = file.readlines()
        
        for line in f:
            split_line = line.split('=')
            ref_dict[split_line[0]] = split_line[1].strip('\n')
    
    return ref_dict


def parent_recursive(ref_dict, images):
    sub_dict = {}

    for value in ref_dict.values():
        if os.path.exists(images + "\\" + value):
            parent = get_commit_id(images + "\\" + value + ".txt", 'parent')

            if os.path.exists(images + "\\" + str(parent) + '.txt'):
                sub_dict[value] = parent
            elif ',' in str(parent):
                sep_parent = parent.split(',')

                if os.path.exists(images + "\\" + sep_parent[0] + '.txt'):
                    sub_dict[value] = sep_parent[0]
                    yield sub_dict
                    yield from parent_recursive(sub_dict, images)

                if os.path.exists(images + "\\" + sep_parent[1] + '.txt'):
                    sub_dict[value] = sep_parent[1]
                    yield sub_dict
                    yield from parent_recursive(sub_dict, images)
                
                sub_dict[value] = parent
    
    if sub_dict != {}:
        yield sub_dict
        yield from parent_recursive(sub_dict, images)


def graph(alll=None):
    images, base_path = find_wit(os.getcwd(), '.wit\\images')
    if base_path:
        references = base_path + "\\.wit\\references.txt"
        print("Drawing a graph, may take a few moments...")
        ref_dict = get_ref_dict(references)
        if alll == '--all':
            for parent in parent_recursive(get_ref_dict(references), images):
                ref_dict.update(parent)
        else:
            ref_dict = {key: value for key, value in ref_dict.items() 
                        if key == 'HEAD' or (key == 'master' and value == ref_dict['HEAD'])}
            for parent in parent_recursive(ref_dict, images):
                ref_dict.update(parent)
        
        print(len(ref_dict))
            
        make_graph(ref_dict)


def branch(name):
    references, base_path = find_wit(os.getcwd(), '.wit\\references.txt')
    if base_path:
        head = get_commit_id(references, 'HEAD')
        branch = get_commit_id(references, name)

        with open(references, 'r+') as file:
            file_lines = file.readlines()
            if branch:
                for index, line in enumerate(file_lines):
                    if line.startswith(name + "="):
                        file_lines[index] = f'{name}={head}\n'
                        print(f'Updated existing branch "{name}"')
            else:
                file_lines.append(f'{name}={head}\n')
            
            file.seek(0)
            file.truncate()
            file.writelines(file_lines)
            

def get_common_commit(head_dict, branch_dict):
    for commit in branch_dict.values():
        if commit in head_dict.values():
            return commit


def merge(branch_name):
    images, base_path = find_wit(os.getcwd(), '.wit\\images')
    if base_path:
        references = base_path + "\\.wit\\references.txt"
        head = get_commit_id(references, 'HEAD')
        is_commit_id = False

        if os.path.exists(images + "\\" + branch_name):
            branch = branch_name
            is_commit_id = True
        else:
            branch = get_commit_id(references, branch_name)
        
        if branch:
            ref_dict_head = parent_recursive({'HEAD': head}, images)
            if is_commit_id and branch in ref_dict_head:
                common_commit = branch
            else:
                ref_dict_branch = parent_recursive({branch_name: branch}, images)
                common_commit = get_common_commit(ref_dict_head, ref_dict_branch)

            if os.path.exists(images + "\\" + common_commit):
                dcmp = filecmp.dircmp(images + "\\" + common_commit, images + "\\" + branch)
                differ_dict = get_diff_files(dcmp, {'common': [], 'to_be_added': []}, images + "\\" + branch)
                staging_area = base_path + '\\.wit\\staging_area\\'

                for file in differ_dict['common'] + differ_dict['to_be_added']:
                    file_path = images + "\\" + branch + "\\" + file
                    if os.path.exists(file_path):
                        if os.path.isfile(file):
                            shutil.copy(file_path, staging_area + file)
                        else:
                            if not os.path.exists(staging_area + file):
                                os.makedirs(staging_area + file)
                            distutils.dir_util.copy_tree(file_path, staging_area + file)

                commit('merge', branch)
            return True
        
        print('Branch does not exist.')
        return False


if len(sys.argv) > 1:
    if sys.argv[1] == 'init':
        init()
    elif sys.argv[1] == 'add':
        add(' '.join(sys.argv[2::]))
    elif sys.argv[1] == 'commit':
        commit(' '.join(sys.argv[2::]))
    elif sys.argv[1] == 'status':
        status()
    elif sys.argv[1] == 'checkout':
        checkout(sys.argv[2])
    elif sys.argv[1] == 'graph':
        if len(sys.argv) > 2:
            graph(sys.argv[2])
        else:
            graph()
    elif sys.argv[1] == 'branch':
        if len(sys.argv) > 2:
            branch(sys.argv[2])
        else:
            print("No branch name specified.")
    elif sys.argv[1] == 'merge':
        if len(sys.argv) > 2:
            merge(sys.argv[2])
        else:
            print("No branch/commit_id specified.")