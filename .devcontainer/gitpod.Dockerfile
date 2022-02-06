FROM gitpod/workspace-full

COPY ./install.sh ./

# Installation
RUN sudo chmod +x ./install.sh && sudo ./install.sh && rm -rf ./install.sh
