## nmap to find CVE's

```sh
# build nmap container
sudo podman build -t nmap .

# runtime nmap
sudo podman run --rm -it --name nmap \
    --net=host --cap-add=net_admin --cap-add=net_raw --cap-add=sys_nice \
    -d nmap

# execute cvss>=5.0 against target IP
sudo podman exec nmap nmap -sV --script vulners --script-args mincvss=5.0 !____ip of target___!

# execute vulscan script against target IP
sudo podman exec nmap nmap -sV --script=vulscan/vulscan.nse !___ip of target___!
```

## _SploitScan

Use SploitScan to find information of found CVE's and available exploits to start pen-testing.  Refer to documentation on how to use in the exploits/_SploitScan directory.