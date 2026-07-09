package main

import (
	"context"
	"fmt"
	"github.com/apache/pulsar-client-go/pulsar"
	"log"
)

func main() {
    client, err := pulsar.NewClient(pulsar.ClientOptions{
        URL: "pulsar://pulsar:6650",
    })

    if err != nil {
        log.Fatalf("Could not instantiate Pulsar client: %v", err)
    }

    defer client.Close()

    producer, err := client.CreateProducer(pulsar.ProducerOptions{
        Topic: "persistent://public/default/my-topic",
    })

    if err != nil {
        log.Fatal(err)
    }

    defer producer.Close()

    for i := 0; i < 10; i++ {
        if msgId, err := producer.Send(context.Background(), &pulsar.ProducerMessage{
            Payload: []byte(fmt.Sprintf("hello-%d", i)),
        }); err != nil {
            log.Fatal(err)
        } else {
            fmt.Printf("Published message: %v \n", msgId)
        }
    }
}