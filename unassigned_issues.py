#
# Lists the unassigned open pull requests and issues at https://github.com/oracle/graal 
#

import sys, os, argparse

import requests # pip install requests

token = os.environ.get("GITHUB_TOKEN")
if token is None:
    raise SystemExit("Set GITHUB_TOKEN environment variable to specify your GitHub personal access token (https://github.com/settings/tokens)")
headers = {"Authorization": "Bearer " + token}

def run_query(query):
    request = requests.post('https://api.github.com/graphql', json={'query': query}, headers=headers)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Query failed to run by returning code of {}. {}".format(request.status_code, query))


def get_open_nodes_query(node_type, cursor=None):
    after = ', after: "{}"'.format(cursor) if cursor is not None else ''
    return """
{
  repositoryOwner(login: "oracle") {
    repository(name: "graal") {
      """ + node_type + """s(first: 100, states:OPEN""" + after + """) {
        totalCount
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            number
            url
            state
            title
            assignees(first: 1) {
              totalCount
            }
          }
        }
      }
    }
  }
}
"""


def get_nodes(node_type):
    all_nodes = {}
    endCursor = None
    sys.stdout.write("Getting " + node_type + "s")
    sys.stdout.flush()
    while True:
        sys.stdout.write(".")
        sys.stdout.flush()
        result = run_query(get_open_nodes_query(node_type, endCursor))
        nodes = result["data"]["repositoryOwner"]["repository"][node_type + "s"]
        edges = nodes["edges"]
        for e in edges:
            node = e["node"]
            all_nodes[node["number"]] = node
        page_info = nodes["pageInfo"]
        if page_info["hasNextPage"] != True:
            break
        else:
            endCursor = page_info["endCursor"]
    sys.stdout.write(os.linesep)
    sys.stdout.flush()
    return all_nodes 

def show_unassigned_nodes(node_type):
    nodes = get_nodes(node_type)
    total_unassigned = 0
    for _, node in sorted(nodes.items()):
        num_assignees = int(node["assignees"]["totalCount"])
        if num_assignees == 0:
            print('  {}: "{}"'.format(node["url"], node["title"]))
            total_unassigned += 1
    print("Total unassigned open " + node_type + "s: " + str(total_unassigned))

def main():
    p = argparse.ArgumentParser()
    p.parse_args()

    show_unassigned_nodes('pullRequest')
    show_unassigned_nodes('issue')

main()
