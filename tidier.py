#!/usr/bin/env python3

import collections
import datetime
import itertools
import os
import re
import sys
import textwrap

import github

NotSet = object()

DEFAULT_COMMENT_FORMAT = """\
This thread is being closed automatically by \
[Tidier](https://github.com/raxod502/tidier) because it is labeled with \
"{label}" and has not seen any activity for {num_days} days. But don't \
worry -- if you have any information that might advance the discussion, \
leave a comment and the thread may be reopened.\
"""


def die(message):
    """
    Print message to stderr and exit with failure.
    """
    print("tidier: " + message, file=sys.stderr)
    sys.exit(1)


def get_environ_var(name, default=NotSet):
    """
    Get value of environment variable with given name. If not set,
    return default. If default is not given, then die and ask the user
    to set the environment variable.
    """
    if name not in os.environ and default is NotSet:
        die("you must set ${}".format(name))
    return os.environ.get(name, default)


def get_issue_repo_name(issue):
    match = re.fullmatch(
        r"https://api.github.com/repos/([^/]+/[^/]+)/issues/[0-9]+", issue.url)
    if not match:
        die("unexpected error response from GitHub API")
    return match.group(1)


token = get_environ_var("TIDIER_ACCESS_TOKEN").strip()
label = get_environ_var("TIDIER_LABEL", default="waiting on response")
include = get_environ_var("TIDIER_INCLUDE_REPOS", default=".*")
exclude = get_environ_var("TIDIER_EXCLUDE_REPOS", default="(?!)")
num_days = get_environ_var("TIDIER_NUM_DAYS", default="90")
comment_format = get_environ_var(
    "TIDIER_COMMENT_FORMAT", default=DEFAULT_COMMENT_FORMAT)
for_real = get_environ_var("TIDIER_FOR_REAL", default="")

try:
    num_days = int(num_days)
except ValueError:
    die("number of days not an integer: {}".format(num_days))

if num_days < 0:
    die("number of days is negative: {}".format(num_days))

if for_real == "0" or "no".startswith(for_real.lower()):
    for_real = ""

if not re.fullmatch(r'[^"]+', label):
    die("unacceptable label name: {}".format(label))

try:
    re.compile(include)
except re.error:
    die("invalid include regex: {}".format(include))

try:
    re.compile(exclude)
except re.error:
    die("invalid exclude regex: {}".format(exclude))

comment_text = comment_format.format(label=label, num_days=num_days)

print("Configuration")
print("  label: {}".format(label))
print("  include regex: {}".format(include))
print("  exclude regex: {}".format(exclude))
print("  number of days: {}".format(num_days))
print("  for real: {}".format("yes" if for_real else "no"))
print("  comment text:")
print(textwrap.indent(textwrap.fill(comment_text), " " * 4))
print()

now = datetime.datetime.utcnow()

print("Timestamp")
print("  {} UTC".format(now))
print()

print('Search for issues for label "{}"'.format(label))
g = github.Github(token)
all_issues = list(g.search_issues('label:"{}" state:open'.format(label)))

all_issues_by_repo = collections.defaultdict(list)
for issue in all_issues:
    all_issues_by_repo[get_issue_repo_name(issue)].append(issue)
print()

print("Retrieve list of repositories to which you have access")
you = g.get_user()
your_username = you.login
your_repo_names = {repo.full_name for repo in you.get_repos()}
print()

print("Check your permissions on the repositories")
issues_by_repo = {}
for repo_name, issues in all_issues_by_repo.items():
    if repo_name not in your_repo_names:
        continue
    print("  Repository {}".format(repo_name))
    match = (
        re.fullmatch(include, repo_name) and
        not re.fullmatch(exclude, repo_name) and
        issues[0].repository.has_in_collaborators(your_username))
    if match:
        print("    Including: you are a collaborator")
        issues_by_repo[repo_name] = issues
    else:
        print("    Not including: you are not a collaborator")
print()

print("Process issues and pull requests")
for repo_name, issues in issues_by_repo.items():
    print("  Repository {}".format(repo_name))
    for issue in issues:
        issue_type = "Pull request" if issue.pull_request else "Issue"
        print("    {} #{}: {}".format(issue_type, issue.number, issue.title))
        how_old = now - issue.updated_at
        if how_old.days >= num_days:
            if for_real:
                print("      Closing: {} days since last activity")
                assert False  # just in case
                # Do this first because it's possible that we can
                # comment but not edit, if the code above doesn't do a
                # good job of filtering out repositories where we
                # aren't collaborators.
                issue.edit(state="closed")
                issue.create_comment(comment_text)
            else:
                print("      Would close: {} days since last activity"
                      .format(how_old.days))
        else:
            print("      Not closing: {} days since last activity"
                  .format(how_old.days))
print()

print("Done!")