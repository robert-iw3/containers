class BaseLogger:
    def __init__(self) -> None:
        self.info = print
        self.error = print

def extract_title_and_question(input_string):
    lines = input_string.strip().split("\n")
    title = ""
    question = ""
    is_question = False
    for line in lines:
        if line.startswith("Title:"):
            title = line.split("Title: ", 1)[1].strip()
        elif line.startswith("Question:"):
            question = line.split("Question: ", 1)[1].strip()
            is_question = True
        elif is_question:
            question += "\n" + line.strip()
    return title, question

def create_vector_index(driver) -> None:
    try:
        driver.query("CREATE VECTOR INDEX stackoverflow IF NOT EXISTS FOR (m:Question) ON m.embedding")
        driver.query("CREATE VECTOR INDEX top_answers IF NOT EXISTS FOR (m:Answer) ON m.embedding")
        driver.query("CREATE FULLTEXT INDEX stackoverflow_fulltext IF NOT EXISTS FOR (q:Question) ON EACH [q.title, q.body]")
    except Exception:
        pass

def create_constraints(driver):
    driver.query(
        "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE"
    )