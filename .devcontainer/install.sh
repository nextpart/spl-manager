#!/bin/bash

KNOWN_DISTRIBUTION="(Alpine|Debian|Ubuntu|RedHat|CentOS)"
DISTRIBUTION=$(lsb_release -d 2>/dev/null | grep -Eo $KNOWN_DISTRIBUTION)

# Detect root user
if [ "$(echo $UID)" = "0" ]; then
	_sudo=''
else
	_sudo='sudo'
fi

# Detect OS / Distribution
if [ -f /etc/alpine-release ]; then
	echo "Hello alpine"
elif [ -f /etc/debian_version -o "$DISTRIBUTION" == "Debian" -o "$DISTRIBUTION" == "Ubuntu" ]; then
	echo "Debian based system"
	apt-get update && apt-get upgrade -y -o Dpkg::Options::="--force-confold" -qq &&
		apt-get install -qqy --fix-missing --no-install-recommends \
			-o APT::Install-Recommends=false \
			-o APT::Install-Suggests=false \
			python3.8 \
			python3-dev \
			python3-pip \
			python3-setuptools \
			build-essential \
      		libjpeg-dev \
			zlib1g-dev &&
		ln -s /usr/bin/python3.8 /usr/bin/python &&
		python -m pip install --upgrade pip setuptools &&
		python -m pip install ansible &&
		apt-get -qy clean autoremove &&
		rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
elif [ -f /etc/redhat-release -o "$DISTRIBUTION" == "RedHat" -o "$DISTRIBUTION" == "CentOS" ]; then
	echo "RedHat based system"
	exit 1
elif [[ -f /etc/os-release && $(grep "^NAME" /etc/os-release | grep -Eo '".*"' | tr -d \") =~ "Amazon Linux" ]]; then
	echo "EC2 - Not supported yet"
	exit 1
elif [[ -f /etc/os-release && $(grep "^NAME" /etc/os-release | grep -Eo '".*"' | tr -d \") =~ "openSUSE" ]]; then
	echo "OpenSuse - Not supported yet"
	exit 1
elif [[ -f /etc/os-release && $(grep "^PRETTY_NAME" /etc/os-release | grep -Eo '".*"' | tr -d \") =~ "SUSE Linux Enterprise" ]]; then
	echo "EnterpriseSuse - Not supported yet"
	exit 1
else
	echo "$(uname -s) - Not supported yet"
	exit 1
fi
