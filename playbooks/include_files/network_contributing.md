
## Debugging network system role

When using the `nm` provider, NetworkManager create a checkpoint and reverts the
changes on failures. This makes it hard to debug the error. To disable this, set
the Ansible variable `__network_debug_flags` to include the value
`disable-checkpoints`. Also tests clean up by default in case there are
failures. They should be tagged as `tests::cleanup` and can be skipped. To use
both, run the test playbooks like this:

```bash
ansible-playbook --skip-tags tests::cleanup \
    -e "__network_debug_flags=disable-checkpoints" \
    -i testhost, tests/playbooks/tests_802_1x.yml
```

### NetworkManager Documentation

[NM 1.0](https://lazka.github.io/pgi-docs/#NM-1.0), it contains a full
explanation about the NetworkManager API.

### Integration tests with podman

1. Create `~/.ansible/collections/ansible_collections/containers/podman/` if this
  directory does not exist and `cd` into this directory.

    ```bash
    mkdir -p ~/.ansible/collections/ansible_collections/containers/podman/
    cd ~/.ansible/collections/ansible_collections/containers/podman/
    ```

2. Clone the collection plugins for Ansible-Podman into the current directory.

    ```bash
    git clone https://github.com/containers/ansible-podman-collections.git .
    ```

3. Change directory into the `tests` subdirectory.

    ```bash
    cd ~/network/tests
    ```

4. Use podman with `-d` to run in the background (daemon). Use `c7` because
  `centos/systemd` is centos7.

    ```bash
    podman run --name lsr-ci-c7 --rm --privileged \
    -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
    -d registry.centos.org/centos/systemd
    ```

5. Use `podman unshare` first to run "podman mount" in root mode, use `-vi` to
  run ansible as inventory in verbose mode, use `-c podman` to use the podman
  connection plugin. NOTE: Some of the tests do not work with podman - see
  `.github/run_test.sh` for the list of tests that do not work.

    ```bash
    podman unshare
    ansible-playbook -vi lsr-ci-c7, -c podman tests_provider_nm.yml
    ```

6. NOTE that this leaves the container running in the background, to kill it:

    ```bash
    podman stop lsr-ci-c7
    podman rm lsr-ci-c7
    ```

