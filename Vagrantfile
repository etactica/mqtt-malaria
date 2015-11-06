# -*- mode: ruby -*-
# vi: set ft=ruby :

# Basic vagrant setup for two bees
# A private network of 192.168.5.x is setup,
# It should be easy to see how to add more vms if you want to experiment

Vagrant.configure("2") do |config|
  servers = {
    :bee1 => "192.168.5.201",
    :bee2 => "192.168.5.202"
  }

  servers.each do |server_id, server_ip|
    config.vm.define server_id do |app_config|
      app_config.vm.box = "hashicorp/precise32"
      app_config.vm.hostname = server_id.to_s
      app_config.vm.network :private_network, ip: server_ip
      app_config.vm.provision :shell, :path => "vagrant.bootstrap.sh"
    end
  end

end
