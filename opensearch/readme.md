<p><a target="_blank" href="https://app.eraser.io/workspace/inTD2pBUBFJpKnEBtlc2" id="edit-in-eraser-github-link"><img alt="Edit in Eraser" src="https://firebasestorage.googleapis.com/v0/b/second-petal-295822.appspot.com/o/images%2Fgithub%2FOpen%20in%20Eraser.svg?alt=media&amp;token=968381c8-a7e7-472a-8ed6-4a6626da5501"></a></p>


![opensearch_graphic.jpg](/.eraser/inTD2pBUBFJpKnEBtlc2___LwMfdHxN5TbOs3GbthKdogHwLmz1___SOSR4KoMtoD-jbnLbU734.jpg "opensearch_graphic.jpg")

OpenSearch is a family of software consisting of a search engine (Apache Lucene
search library) that can handle massive amounts of data, are highly scalable, and can support millisecond response times. Architected to handle node and data center failures, they provide high availability and reliability for your production workload. OpenSearch Dashboards is a data visualization dashboard for that search engine.



![diagram-export-12-4-2023-4_07_14-PM.png](/.eraser/inTD2pBUBFJpKnEBtlc2___LwMfdHxN5TbOs3GbthKdogHwLmz1___vNDeSBw2G2fdDMn5Ygz5l.png "diagram-export-12-4-2023-4_07_14-PM.png")

```sh

# Update creds
vim .creds.curlrc

# Generate certs
certs/generate-certificates.sh

# Update Cert Fields in "opensearch.yml"
vim opensearch.yml

# Compose up Opensearch / Dashboards
podman-compose up -d

```


<!--- Eraser file: https://app.eraser.io/workspace/inTD2pBUBFJpKnEBtlc2 --->