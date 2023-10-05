.github - common file and configuration management for system roles
===================================================================

The configuration source for linux-system-roles repositories.  This uses Ansible
to manage configuration, github actions, and other common files used by
repositories in the linux-system-roles organization.  This allows org admins to
easily rollout updates to all repos.

File structure
--------------

The structure of the files/directories under `playbooks/files` and
`playbooks/templates` should match exactly the name and location of the
files/directories in the role repositories.  For example,
`playbooks/templates/.ansible-lint` corresponds to the `.ansible-lint` file in
the root directory of the role repositories.
`playbooks/.github/workflows/weekly_ci.yml` corresponds to the file
`.github/workflows/weekly_ci.yml` in the role repositories.

The file `inventory.yml` is the list of all roles and contains the groups
`active_roles` for all of the actively maintained and supported roles, and the
group `python_roles` for the roles that provide Ansible python plugins such as
modules, filters, etc.

The file `inventory/group_vars/active_roles.yml` is used for settings common to
all roles.

The file `inventory/group_vars/python_roles.yml` is used for settings common to
all roles that have python modules, filters, and other Ansible plugin python
code.

The file `inventory/host_vars/$ROLENAME.yml` is used for settings that are
specific to that role.  Some examples:

* The scheduled time for a github action
* .ansible-lint or .yamllint.yml customizations

Add a new role
--------------

* Edit inventory.yml
* Add the role in alphabetical order to the `all.hosts` section:

```yaml
all:
  hosts:
    ...
    postgresql:
      ansible_host: localhost
    quite_a_good_new_role:
      ansible_host: localhost
    rhc:
      ansible_host: localhost
```

* Add the role to the `active_roles.hosts` section:

```yaml
        postgresql:
        quite_a_good_new_role:
        rhc:
```

* If the role has python modules or filters or other plugins,
  add to the `python_roles.hosts` section:

```yaml
        network:
        quite_a_good_new_role:
        selinux:
```

* Add the new file `inventory/host_vars/$ROLENAME.yml` - add any customizations
  for the github actions weekly_ci, ansible_lint, etc.

Add a new config or github action file
--------------------------------------

* Add the file under `playbooks/files` or `playbooks/templates`

Add the file according to the location in the role repository under
`playbooks/files` or `playbooks/templates`.  If the file is static, and needs no
per-role configuration (such as a github action cron schedule), then add under
`playbooks/files`.

NOTE: github action files will almost always be templates, due to the checkout
action being template-ized.

* Add the file to the appropriate list in
  `inventory/group_vars/active_roles.yml` or
  `inventory/group_vars/python_roles.yml`

`present_templates` are files that should be present in all roles that are
generated by templates.
`present_files` are files that should be present in all roles that are static.
`absent_files` are files that should be removed from all roles.
`present_python_templates` are files that should be present in roles that
provide Ansible python code that are generated by templates.
`present_python_files` are files that should be present in roles that provide
Ansible python code that are static.
`absent_python_files` are files that should be removed from roles that provide
Ansible python code.

Preparing for using the automation
----------------------------------

This uses the [gh](https://cli.github.com/) command line tool provided by the
`gh` package on Fedora.
To configure Github tools to run the automation, complete the following steps:

* Configure `gh` to authenticate to github using `~/.config/gh/hosts.yml`:

    ```yaml
    github.com:
      user: my_user_name
      oauth_token: my_oauth_token
      git_protocol: ssh
    ```

    Or by running interactive `gh auth login`.

* Configure credentials caching by running:

    ```
    $ git config --global credential.helper cache
    ```

    The next time GitHub asks you to log in, use your username and auth token.

Creating PRs in every role with updated files
---------------------------------------------

The playbook `playbooks/update_files.yml` will create PRs in all roles with the
new/updated/deleted files.
If you just want to see what the playbook will do without actually creating
anything on github, add `-e lsr_dry_run=true` to the ansible-playbook command.

### Parameters

* `update_files_commit_file` - REQUIRED, no default - This is the path to the
  file containing the git commit message to use for the commit, and will also be
  used as the PR title and body.  Please use good practices for creating the
  commit message as described in
  [Contributing](https://linux-system-roles.github.io/contribute.html) under
  "Write a good commit message".
* `update_files_branch` - default "update_role_files" - this is the name of the
  git branch that will be used for the PR.  You probably don't want to change
  this unless you have some conflict.
* `lsr_dry_run` - default `true` - use `false` to actually push and create PRs
* `test_dir` - default none - if you specify this, the playbook will checkout
  the role directories under this directory - by default, the playbook will
  create and remove a tmpdir
* `exclude_roles` - default none - you can specify a comma-delimited list of
  roles to exclude from processing.  This is useful when you want to update
  all roles *except* the given roles.
* `include_roles` - default none - you can specify a comma-delimited list of
  roles to include in processing, and all other roles will be excluded.  This
  is useful when you want to update *only* the given roles, and exclude the
  rest.  NOTE: `include_roles` currently only works with 1 role at a time.
  You cannot currently specify a list of roles.

### Run it

Run it like this:

```
ansible-playbook -vv -i inventory -e lsr_dry_run=false \
  -e update_files_branch=my_update_branch -e exclude_roles=nbde_client \
  -e test_dir=/var/tmp/lsr \
  -e update_files_commit_file=/path/to/git-commit-msg playbooks/update_files.yml
```

### How it works

* A temp directory is created if `test_dir` is not specified
* All of the roles are cloned into that directory, except for the roles
  listed in `exclude_roles`
* Figure out the name of the main branch
* If the branch `update_files_branch` does not exist, it is
  created from the main branch
* If the branch `update_files_branch` already exists, it will
  be rebased on top of the main branch
* Add/update/remove the files to be managed in each role
* If there are no updates to be done, just exit
* Create a git commit using `update_files_commit_file` for the message
* Push the commit to `update_files_branch` in `github.com/linux-system-roles/$ROLE`
  If the branch already exists, it will be pushed with `git push -f`
* Create the PR if it doesn't already exist
* Wait for review feedback

NOTE: This process may create multiple commits if you need to make edits to an
existing PR.  Use the `Squash commits and merge` functionality in the github PR
to merge.
