# Step 1. Generate backend openapi spec, modify docker-compose.yaml to mount that spec.
```sh
#create your backend api spec, example:
tee ./myopenapi3-spec.json <<\EOF
openapi: 3.0.0
info:
  version: 1.0.0
  title: Simple API
  description: A simple API to illustrate OpenAPI concepts

servers:
  - url: https://example.io/v1

security:
  - BasicAuth: []

paths:
  /artists:
    get:
      description: Returns a list of artists
      parameters:
        #  ----- Added line  ------------------------------------------
        - $ref: '#/components/parameters/PageLimit'
        - $ref: '#/components/parameters/PageOffset'
        #  ---- /Added line  ------------------------------------------
      responses:
        '200':
          description: Successfully returned a list of artists
          content:
            application/json:
              schema:
                type: array
                items:
                  #  ----- Added line  --------------------------------
                  $ref: '#/components/schemas/Artist'
                  #  ---- /Added line  --------------------------------
        '400':
          #  ----- Added line  ----------------------------------------
          $ref: '#/components/responses/400Error'
          #  ---- /Added line  ----------------------------------------

    post:
      description: Lets a user post a new artist
      requestBody:
        required: true
        content:
          application/json:
            schema:
              #  ----- Added line  ------------------------------------
              $ref: '#/components/schemas/Artist'
              #  ---- /Added line  ------------------------------------
      responses:
        '200':
          description: Successfully created a new artist
        '400':
          #  ----- Added line  ----------------------------------------
          $ref: '#/components/responses/400Error'
          #  ---- /Added line  ----------------------------------------

  /artists/{username}:
    get:
      description: Obtain information about an artist from his or her unique username
      parameters:
        - name: username
          in: path
          required: true
          schema:
            type: string

      responses:
        '200':
          description: Successfully returned an artist
          content:
            application/json:
              schema:
                type: object
                properties:
                  artist_name:
                    type: string
                  artist_genre:
                    type: string
                  albums_recorded:
                    type: integer

        '400':
          #  ----- Added line  ----------------------------------------
          $ref: '#/components/responses/400Error'
          #  ---- /Added line  ----------------------------------------

components:
  securitySchemes:
    BasicAuth:
      type: http
      scheme: basic

  schemas:
    Artist:
      type: object
      required:
        - username
      properties:
        artist_name:
          type: string
        artist_genre:
            type: string
        albums_recorded:
            type: integer
        username:
            type: string

  #  ----- Added lines  ----------------------------------------
  parameters:
    PageLimit:
      name: limit
      in: query
      description: Limits the number of items on a page
      schema:
        type: integer

    PageOffset:
      name: offset
      in: query
      description: Specifies the page number of the artists to be displayed
      schema:
        type: integer

  responses:
    400Error:
      description: Invalid request
      content:
        application/json:
          schema:
            type: object
            properties:
              message:
                type: string
  #  ---- /Added lines  ----------------------------------------
EOF

#create your denied tokens if any, example:
tee ./tokens.denylist.db <<\EOF
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzb21lIjoicGF5bG9hZDk5OTk5ODIifQ.CUq8iJ_LUzQMfDTvArpz6jUyK0Qyn7jZ9WCqE0xKTCA
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzb21lIjoicGF5bG9hZDk5OTk5ODMifQ.BinZ4AcJp_SQz-iFfgKOKPz_jWjEgiVTb9cS8PP4BI0
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzb21lIjoicGF5bG9hZDk5OTk5ODQifQ.j5Iea7KGm7GqjMGBuEZc2akTIoByUaQc5SSX7w_qjY8
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzb21lIjoicGF5bG9hZDk5OTk5ODUifQ.S9P-DEiWg7dlI81rLjnJWCA6h9Q4ewTizxrsxOPGmNA
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzb21lIjoicGF5bG9hZDk5OTk5ODYifQ.HdINfOmk59NdNYBnMjrqUdD4gEikAUafKjAhBI1_Ue8
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzb21lIjoicGF5bG9hZDk5OTk5ODcifQ.MDPMmuAquxi55sGTajKQjcFzoaNzFZJFMkDg3fIyhx0
EOF

```

> **Note**
>
> Following instructions are for using the wallarm image
>
>

# Step 2. Configure the Docker network
https://docs.wallarm.com/api-firewall/installation-guides/docker-container/#step-2-configure-the-docker-network
# Step 3. Configure the application to be protected with API Firewall
https://docs.wallarm.com/api-firewall/installation-guides/docker-container/#step-3-configure-the-application-to-be-protected-with-api-firewall
# Step 4. Configure API Firewall
https://docs.wallarm.com/api-firewall/installation-guides/docker-container/#step-4-configure-api-firewall
# Step 5. Deploy the configured environment
To build and start the configured environment, run the following command:
```sh
podman-compose up -d --force-recreate
```
To check the log output:
```sh
podman-compose logs -f
```
# Step 6. Test API Firewall operation
```
To test API Firewall operation, send the request that does not match the mounted Open API 3.0 specification to the API Firewall Docker container address.

For example, you can pass the string value in the parameter that requires the integer value.

If the request does not match the provided API schema, the appropriate ERROR message will be added to the API Firewall Docker container logs.
```
Step 7. Enable traffic on API Firewall

To finalize the API Firewall configuration, please enable incoming traffic on API Firewall by updating your application deployment scheme configuration.

For example, this would require updating the Ingress, NGINX, or load balancer settings.

Using docker run to start API Firewall
To start API Firewall on Docker, you can also use regular Docker commands as in the examples below:

To create a separate Docker network to allow the containerized application and API Firewall communication without manual linking:
```sh
podman network create api-firewall-network
```
To start the containerized application to be protected with API Firewall:
```sh
podman run --rm -it --network api-firewall-network \
    --network-alias backend -p 8090:8090 <myapp:tag>
```
To start API Firewall:
```sh
podman run --rm -it --network api-firewall-network --network-alias api-firewall \
    -v <HOST_PATH_TO_SPEC>:<CONTAINER_PATH_TO_SPEC> -e APIFW_API_SPECS=<PATH_TO_MOUNTED_SPEC> \
    -e APIFW_URL=<API_FIREWALL_URL> -e APIFW_SERVER_URL=<PROTECTED_APP_URL> \
    -e APIFW_REQUEST_VALIDATION=<REQUEST_VALIDATION_MODE> -e APIFW_RESPONSE_VALIDATION=<RESPONSE_VALIDATION_MODE> \
    -p 8088:8088 wallarm/api-firewall:v0.6.13
```

## How it works:

<img src="https://raw.githubusercontent.com/wallarm/api-firewall/main/images/Firewall%20opensource%20-%20vertical.gif" width=50% height=50%>
