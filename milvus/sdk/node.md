```sh

npm install @zilliz/milvus2-sdk-node

```

```javascript

import { MilvusClient, DataType } from '@zilliz/milvus2-sdk-node';

const address = 'your-milvus-ip-with-port';
const username = 'your-milvus-username'; // optional username
const password = 'your-milvus-password'; // optional password

// connect to milvus
const client = new MilvusClient({ address, username, password });

// define schema
const collection_name = `hello_milvus`;
const dim = 128;
const schema = [
  {
    name: 'age',
    description: 'ID field',
    data_type: DataType.Int64,
    is_primary_key: true,
    autoID: true,
  },
  {
    name: 'vector',
    description: 'Vector field',
    data_type: DataType.FloatVector,
    dim: 8,
  },
  { name: 'height', description: 'int64 field', data_type: DataType.Int64 },
  {
    name: 'name',
    description: 'VarChar field',
    data_type: DataType.VarChar,
    max_length: 128,
  },
],

await client.createCollection({
  collection_name,
  fields: schema,
});

// prepare data

const fields_data = [
  {
    vector: [
      0.11878310581111173, 0.9694947902934701, 0.16443679307243175,
      0.5484226189097237, 0.9839246709011924, 0.5178387104937776,
      0.8716926129208069, 0.5616972243831446,
    ],
    height: 20405,
    name: 'zlnmh',
  },
  {
    vector: [
      0.9992090731236536, 0.8248790611809487, 0.8660083940881405,
      0.09946359318481224, 0.6790698063908669, 0.5013786801063624,
      0.795311915725105, 0.9183033261617566,
    ],
    height: 93773,
    name: '5lr9y',
  },
  {
    vector: [
      0.8761291569818763, 0.07127366044153227, 0.775648976160332,
      0.5619757601304878, 0.6076543120476996, 0.8373907516027586,
      0.8556140171597648, 0.4043893119391049,
    ],
    height: 85122,
    name: 'nes0j',
  },
];

// insert data into collection

await client.insert({
  collection_name,
  fields_data,
});

// create index
await client.createIndex({
  // required
  collection_name,
  field_name: 'vector', // optional if you are using milvus v2.2.9+
  index_name: 'myindex', // optional
  index_type: 'HNSW', // optional if you are using milvus v2.2.9+
  params: { efConstruction: 10, M: 4 }, // optional if you are using milvus v2.2.9+
  metric_type: 'L2', // optional if you are using milvus v2.2.9+
});

// load collection
await client.loadCollectionSync({
  collection_name,
});

// get the search vector
const searchVector = fields_data[0].vector;

// Perform a vector search on the collection
const res = await client.search({
  // required
  collection_name, // required, the collection name
  vector: searchVector, // required, vector used to compare other vectors in milvus
  // optionals
  filter: 'height > 0', // optional, filter
  params: { nprobe: 64 }, // optional, specify the search parameters
  limit: 10, // optional, specify the number of nearest neighbors to return
  metric_type: 'L2', // optional, metric to calculate similarity of two vectors
  output_fields: ['height', 'name'], // optional, specify the fields to return in the search results
});

```
