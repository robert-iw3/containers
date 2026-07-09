## So Now You Know.

<p align="center">
  <img src="https://snyk.io/_next/static/media/default-snyk.6bb9b598.jpg" />
</p>

[What is snyk?](https://snyk.io/)

a) Sign-up for snyk: https://app.snyk.io/login

b) Generate Token in "Account Settings":

<p align="center">
  <img src="imgs/snykauthtoken.png" />
</p>

c) Modify the SNYK_API variable with the Auth Token Key in the Dockerfile.

d) Modify the URL and CODE_NAME arguments in the Dockerfile.


>
> **Note**
>
> The "snyk monitor" command sends the results to your projects in https://app.snyk.io/org/<Your Username>


## Example view of the UI:

<p align="center">
  <img src="imgs/snykdashboard.png" />
</p>

## Dependencies / Modules Vulnerabilities example:

<p align="center">
  <img src="imgs/issuesexample.png" />
</p>

## Vulnerability Coverage example:

<p align="center">
  <img src="imgs/vulntypes.png" />
</p>

## Fix Analysis example:

<p align="center">
  <img src="imgs/fixanalysis.png" />
</p>
