## RAG Breakdown

Retrieval-Augmented Generation

The GenAI Stack allows you to use RAG to improve the accuracy and relevance of the generated results from the GenAI app.

Retrieval-augmented generation is a technique that combines retrieval mechanisms with generative AI models to improve the quality and relevance of generated content. Unlike traditional generative models that rely solely on the data they were trained on, RAG systems first retrieve relevant information from an external knowledge base or dataset and then use this information to inform and enhance the output generated.

The response generation process in a RAG system involves two steps:

    Retrieval – The system searches through a knowledge source, such as a database, to find the most relevant information related to the input query.
    Generation – The retrieved information is then fed into a generative model, which uses this context to produce a more accurate and contextually relevant response.

The information retrieval step of a RAG system involves the following:

    User query embedding – The RAG system transforms the user's natural language query into a vector representation, known as an embedding. This embedding captures the semantic meaning of the query, enabling the system to understand nuances, context, and intent beyond simple keyword matching.
    Similar document retrieval – The system performs a vector search across a knowledge graph or a document repository using the embedded query. Since this search uses a vector representation of the query, it identifies documents that conceptually align with the query, not just those with exact keyword matches.
    Context extraction – The system optionally analyzes the relationships between different pieces of information in the documents (or in graph databases, nodes and relationships retrieved from the graph) to provide a more informed and contextually accurate answer.
    Enhanced prompt creation – The system combines the user query, the retrieved information, and any other specific instructions into a detailed prompt for the LLM.

In the generation step, the LLM generates a response using this enhanced prompt to produce an answer with more context compared to answering based on only its pre-trained knowledge.

RAG offers several benefits. It grounds LLM responses in factual data from external knowledge sources, which reduces the risk of generating incorrect information and improves factual accuracy. Because RAG retrieves and uses the most relevant information, it also increases the relevance of responses. Unlike LLMs, RAG has access to the relevant documents from where it sourced data during response generation. This means it can share the sources of information it uses, which allows users to verify the accuracy and relevance of the AI's output.

Later in this blog, you'll be able to see the difference in the quality of responses with and without RAG in the support agent.

## Graph DB input

The application served on http://localhost:8502 is a data import application that lets you import Stack Overflow question-answer data into the Neo4j data store.

<p align="center">
  <img src="https://dist.neo4j.com/wp-content/uploads/20231005063102/import-embed-data-stack-overflow.png" width="400" />
</p>

Pick any tag here and set the number of pages somewhere between 5 and 10, then click Import to start importing the data.

<p align="center">
  <img src="https://dist.neo4j.com/wp-content/uploads/20231005063128/stack-overflow-loader-1536x1011.png" width="400" />
</p>

locale:

http://localhost:7474 and log in with username neo4j and password password, as configured in the Docker Compose file. Once logged in, you can see an overview in the left sidebar of the webpage and view some connected data by clicking the pill with the counts.

<p align="center">
  <img src="https://dist.neo4j.com/wp-content/uploads/20241105020735/Overview-extracted-data-2048x1021.png" width="1200" />
</p>

The application served on http://localhost:8501 has a classic LLM chat UI that lets you ask questions and get answers.

<p align="center">
  <img src="https://dist.neo4j.com/wp-content/uploads/20241113110220/chat-agent-ui.png" width="1200" />
</p>

The chat agent uses a vector similarity search and graph traversal tool to first retrieve relevant documents from the Neo4j graph database and then feeds the documents and the query to the LLM.

<p align="center">
  <img src="https://dist.neo4j.com/wp-content/uploads/20231005063228/query-imported-data.png" width="600" />
</p>

RAG Enabled return:

<p align="center">
  <img src="https://dist.neo4j.com/wp-content/uploads/20231005063244/input-answer-sources.png" width="600" />
</p>