# Sample CDK Stack with Docker container

Based on [Official CDK docs](https://docs.aws.amazon.com/cdk/latest/guide/ecs_example.html)

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful commands

- `npm run build` compile typescript to js
- `npm run watch` watch for changes and compile
- `cdk deploy` deploy this stack to your default AWS account/region
- `cdk diff` compare deployed stack with current state
- `cdk synth` emits the synthesized CloudFormation template

## Setting ENV variables

Specify enviroment variables in file `.env.sh`:

```sh
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export ACCOUNT_ID=...
export REGION=us-west-1
```

Load env into current shell

```sh
source .env.sh
```

After this step, all `cdk xxx` steps would be able to use provided AWS Account

## Troubleshooting

If `cdk` fails for any reason make sure you did [bootstrap](https://docs.aws.amazon.com/cdk/latest/guide/tools.html) cdk: `cdk bootstrap`

## Notes

https://docs.aws.amazon.com/cdk/latest/guide/ecs_example.html
