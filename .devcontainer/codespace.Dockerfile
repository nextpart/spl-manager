
FROM mcr.microsoft.com/vscode/devcontainers/universal:1-focal

# Prepare Ansible environment
WORKDIR /workspace

COPY ./install.sh ./

# Installation
RUN sudo chmod +x ./install.sh && sudo ./install.sh && rm -rf ./install.sh


# Gitpod prebuild equivalent
USER root
ARG playbook=setup
COPY --chmod=755 ./ansible /ansible
RUN ansible-galaxy role install -r /ansible/roles/requirements.yml ; \
    ansible-playbook -c local -v "/ansible/playbooks/${playbook}.yml" -e username=gitpod -K

USER codespace
