.DEFAULT_GOAL := bootstrap
ANSIBLE_DIR := ./ansible
PB_DIR := ./playbooks

K8S_APP ?= taskmanager

ENV_FILE ?= $(abspath ansible/environment.yml)
# Public checkouts use their own credentials; a local vault file is optional.
VAULT_ARGS ?= $(if $(wildcard ansible/secrets/vault_pass.txt),--vault-password-file $(abspath ansible/secrets/vault_pass.txt),)
EXTRA_ARGS ?=
ENV_ARGS = -e '@$(ENV_FILE)' $(VAULT_ARGS) $(EXTRA_ARGS)
BOOTSTRAP_ARGS = -i inventories/bootstrap/hosts.yml $(ENV_ARGS) -v
PROD_ARGS = -i inventories/prod/hosts.yml $(ENV_ARGS) -v

bootstrap:
	cd $(ANSIBLE_DIR) && ansible-playbook $(BOOTSTRAP_ARGS) $(PB_DIR)/00-bootstrap.yml \
	--tags bootstrap
prepare_lab:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/10-lab-prepare.yml \
	--tags lab_prepare

create_mainhost:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/20-lab-create-mainhost.yml

prepare_mainhost:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/30-mh-prepare.yml

create_vms:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/40-mh-create-k3s-vms.yml \
	--tags create_vms $(if $(LIMIT),--limit $(LIMIT),)

prepare_vms:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/50-k3s-prepare.yml \
	--tags prepare_vms $(if $(LIMIT),--limit $(LIMIT),)

stop_k3s_vms:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/200-mh-stop-k3s-vms.yml

clean_k3s_vms:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/201-mh-clean-k3s-vms.yml

stop_mainhost:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/202-lab-stop-mainhost.yml

clean_mainhost:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/203-lab-clean-mainhost.yml

shutdown_lab:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/204-lab-shutdown.yml

shutdown:
	-$(MAKE) stop_k3s_vms
	-$(MAKE) stop_mainhost
	-$(MAKE) shutdown_lab

reset_and_shutdown:
	-$(MAKE) clean_k3s_vms
	-$(MAKE) clean_mainhost
	$(MAKE) shutdown_lab

bootstrap_k3s:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/60-k3s-bootstrap.yml \
	$(if $(LIMIT),--limit $(LIMIT),)

kubeconfig_mainhost:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/61-k3s-kubeconfig.yml

k8s_sync:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/70-k3s-app.yml -e k8s_app=$(K8S_APP) -e k8s_action=sync

k8s_apply:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/70-k3s-app.yml -e k8s_app=$(K8S_APP) -e k8s_action=apply

k8s_delete:
	cd $(ANSIBLE_DIR) && ansible-playbook $(PROD_ARGS) $(PB_DIR)/70-k3s-app.yml -e k8s_app=$(K8S_APP) -e k8s_action=delete

taskmanager_sync:
	$(MAKE) k8s_sync K8S_APP=taskmanager

taskmanager_apply:
	$(MAKE) k8s_apply K8S_APP=taskmanager

taskmanager_delete:
	$(MAKE) k8s_delete K8S_APP=taskmanager

check_config:
	cd $(ANSIBLE_DIR) && ansible-playbook -i localhost, -e '@$(ENV_FILE)' $(PB_DIR)/05-config-check.yml

.PHONY: bootstrap prepare_lab create_mainhost prepare_mainhost create_vms prepare_vms stop_k3s_vms clean_k3s_vms stop_mainhost clean_mainhost shutdown_lab shutdown reset_and_shutdown bootstrap_k3s kubeconfig_mainhost k8s_sync k8s_apply k8s_delete taskmanager_sync taskmanager_apply taskmanager_delete check_config
bootstrap prepare_lab create_mainhost prepare_mainhost create_vms prepare_vms stop_k3s_vms clean_k3s_vms stop_mainhost clean_mainhost shutdown_lab shutdown reset_and_shutdown bootstrap_k3s kubeconfig_mainhost k8s_sync k8s_apply k8s_delete taskmanager_sync taskmanager_apply taskmanager_delete: check_config
