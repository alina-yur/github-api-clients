#!/usr/bin/env python3
#
# Reports following for https://github.com/oracle/graal:
#
# * Open issues and pull requests without a comment by someone in the https://github.com/oracle org in the last 30 days.
# * Open issues and pull requests that are unassigned.
#
import sys, os, json, urllib.request, datetime, traceback

token = os.environ.get("GITHUB_TOKEN")
if token is None:
    raise SystemExit("Set GITHUB_TOKEN environment variable to specify your GitHub personal access token (https://github.com/settings/tokens)")
headers = {"Authorization": "Bearer " + token}

def run_query(query):
    req = urllib.request.Request(url='https://api.github.com/graphql', data=json.dumps({'query' : query}).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as f:
        if f.status == 200:
            result = f.read().decode('utf-8')
            return json.loads(result)
        else:
            raise Exception("Query failed to run by returning code of {}. {}".format(f.status, query))

_node_info1 = """
number
url
title
assignees(first: 1) {
  totalCount
}
timelineItems(last:10) {
  edges {
    node {
      ... on IssueComment {
        updatedAt
        url
        author {
          ... on User {
              organization(login: "oracle") {
              login
            }
          }
          login
        }
      }
    }
  }
}
"""

def get_open_nodes_query(node_type, node_info, states, cursor=None):
    after = '"{}"'.format(cursor) if cursor else 'null'
    return """
{
  repositoryOwner(login: "oracle") {
    repository(name: "graal") {
      """ + node_type + """s(first: 100, states:""" + states + """, after:""" + after + """) {
        totalCount
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {""" + node_info + """ }
        }
      }
    }
  }
}
"""

_cached_results = {}

def get_nodes(node_type, node_info, states):
    key = node_type + node_info
    if key in _cached_results:
        return _cached_results[node_type]
    all_nodes = {}
    endCursor = None
    sys.stdout.write("Getting " + node_type + "s")
    sys.stdout.flush()
    while True:
        sys.stdout.write(".")
        sys.stdout.flush()
        result = run_query(get_open_nodes_query(node_type, node_info, states, endCursor))
        try:
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
        except KeyError as e:
            traceback.print_exc()
            print(result)
            raise SystemExit()
    sys.stdout.write(os.linesep)
    sys.stdout.flush()
    _cached_results[key] = all_nodes
    return all_nodes 

def show_unassigned_nodes(node_type):
    nodes = get_nodes(node_type, _node_info1, states='OPEN')
    total_unassigned = 0
    print("====================================================================================================")
    print("Unassigned open " + node_type + "s")
    print("====================================================================================================")
    for _, node in sorted(nodes.items(), reverse=True):
        num_assignees = int(node["assignees"]["totalCount"])
        if num_assignees == 0:
            print('{}: "{}"'.format(node["url"], node["title"]))
            total_unassigned += 1
    print("Total unassigned open " + node_type + "s: " + str(total_unassigned))
    print()

def parse_datetime(s):
    if s.endswith('Z'):
        s = s[0:-1]
    return datetime.datetime.fromisoformat(s)

def show_no_recent_activity_nodes(node_type):
    nodes = get_nodes(node_type, _node_info1, states='OPEN')
    now = datetime.datetime.now()
    print("====================================================================================================")
    print("Open " + node_type + "s that have not been commented on by an Oracle employee for more than 30 days")
    print("====================================================================================================")
    for _, node in sorted(nodes.items(), reverse=True):
        timeline = node["timelineItems"]
        last_oracle_comment = None
        for edge in timeline["edges"]:
            item = edge["node"]
            if item:
                author = item["author"]
                if author and author["organization"]:
                    # guaranteed to be "oracle" organization
                    if last_oracle_comment is None:
                        last_oracle_comment = (item["url"], parse_datetime(item["updatedAt"]))
                    else:
                        url, previous_updated_at = last_oracle_comment
                        updated_at = parse_datetime(item["updatedAt"])
                        if updated_at > previous_updated_at:
                            last_oracle_comment = (item["url"], updated_at)

        if not last_oracle_comment:
            print('{}: "{}" (no Oracle comments)'.format(node["url"], node["title"]))
        else:
            url, updated_at = last_oracle_comment
            delta = now - updated_at
            if delta.days > 30:
                print('{}: "{}" ({} days, {})'.format(node["url"], node["title"], delta.days, url))
    print()

_node_info2 = """
number
author {
  ... on User {
    login
    organizations(first:5) {
      edges {
        node {
          login
        }
      }
    }
  }
}
createdAt
closedAt
"""

def show_nodes_opened_per_year(node_type):
    states = '[OPEN,CLOSED,MERGED]' if node_type == 'pullRequest' else '[OPEN,CLOSED]'
    nodes = get_nodes(node_type, _node_info2, states=states)
    now = datetime.datetime.now()
    print("====================================================================================================")
    print(node_type + "s opened per year")
    print("====================================================================================================")
    opened_per_year = {}
    for node in nodes.values():
        author = node["author"]
        if author:
            created_at = parse_datetime(node["createdAt"])
            orgs = frozenset([e["node"]["login"] for e in author["organizations"]["edges"]])
            opened = opened_per_year.setdefault(created_at.year, {})
            key = "oracle" if "oracle" in orgs else "other"
            opened[key] = opened.get(key, 0) + 1
    for year, opened in opened_per_year.items():
        counts = '\t'.join('{}={}'.format(label, value) for label, value in sorted(opened.items()))
        print('{}: {}'.format(year, counts))
    print()

show_no_recent_activity_nodes('issue')
show_no_recent_activity_nodes('pullRequest')

show_unassigned_nodes('pullRequest')
show_unassigned_nodes('issue')

show_nodes_opened_per_year('issue')
show_nodes_opened_per_year('pullRequest')
