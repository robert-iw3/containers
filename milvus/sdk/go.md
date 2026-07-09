```sh

go get -u github.com/milvus-io/milvus-sdk-go/v2

```

```go

import "github.com/milvus-io/milvus-sdk-go/v2/client"

//...other snippet ...
client, err := client.NewClient(context.Background(), client.Config{
   Address: "localhost:19530",
})
if err != nil {
    // handle error
}
defer client.Close()

client.HasCollection(context.Background(), "YOUR_COLLECTION_NAME")

```
