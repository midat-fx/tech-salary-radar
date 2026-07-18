"""Canonical skill catalog — exactly 61 skills. Exhaustive; do NOT edit (see PLAN.md §6.1)."""

SKILLS = {
    "Python": ["python3", "питон"], "SQL": ["t-sql", "pl/sql"],
    "JavaScript": ["js", "джаваскрипт"], "TypeScript": ["ts"],
    "Java": ["джава"], "Kotlin": [], "Go": ["golang"], "C#": ["c sharp", "csharp"],
    "C++": ["cpp"], "PHP": [], "1C": ["1с", "1с:предприятие", "1с предприятие", "1c:enterprise"],
    "Bash": ["shell", "shell scripting"],
    "pandas": [], "PyTorch": ["torch"], "TensorFlow": ["keras"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "Machine Learning": ["ml", "машинное обучение", "deep learning", "глубокое обучение"],
    "Computer Vision": ["cv", "компьютерное зрение", "opencv"],
    "NLP": ["natural language processing", "обработка естественного языка"],
    "LLM": ["genai", "generative ai", "large language models", "генеративный ии"],
    "RAG": ["retrieval augmented generation"],
    "LangChain": ["langgraph"], "MLOps": ["mlflow"],
    "Airflow": ["apache airflow"], "Spark": ["apache spark", "pyspark"],
    "Kafka": ["apache kafka"], "ClickHouse": [],
    "Power BI": ["powerbi", "power-bi"], "Tableau": [], "Excel": ["ms excel", "microsoft excel"],
    "Django": [], "FastAPI": ["fast api"], "Flask": [],
    "Spring": ["spring boot"], "Node.js": ["nodejs", "node", "express", "nestjs", "nest.js"],
    ".NET": ["dotnet", "asp.net", ".net core"], "REST API": ["rest", "restful"], "GraphQL": [],
    "React": ["reactjs", "react.js", "next.js", "nextjs"],
    "Vue": ["vuejs", "vue.js", "nuxt"], "Angular": [],
    "HTML/CSS": ["html", "css", "html5", "css3", "верстка", "вёрстка", "адаптивная верстка"],
    "Flutter": ["dart"], "React Native": ["react-native"],
    "Docker": ["docker compose", "docker-compose"], "Kubernetes": ["k8s", "helm"],
    "Linux": ["ubuntu", "unix"], "Git": ["github", "gitlab"],
    "CI/CD": ["cicd", "ci cd", "gitlab ci", "github actions", "jenkins", "teamcity"],
    "Terraform": [], "Nginx": [], "AWS": ["amazon web services"], "Grafana": ["prometheus"],
    "PostgreSQL": ["postgres"], "MySQL": [], "MongoDB": ["mongo"], "Redis": [],
    "MS SQL Server": ["ms sql", "mssql", "sql server", "microsoft sql server"],
    "Elasticsearch": ["elastic", "opensearch"],
    "n8n": [], "Selenium": ["selenium webdriver"],
}
CANONICAL = list(SKILLS)

# ALIAS_TO_CANON: casefold map of canonical names and aliases -> canonical.
ALIAS_TO_CANON = {}
for _canon, _aliases in SKILLS.items():
    ALIAS_TO_CANON[_canon.casefold()] = _canon
    for _alias in _aliases:
        ALIAS_TO_CANON[_alias.casefold()] = _canon


def canonicalize(raw):
    """Map a raw skill string to its canonical form by EXACT match (not substring).

    Returns the canonical name, or None if the input is not a known skill/alias.
    """
    if raw is None:
        return None
    return ALIAS_TO_CANON.get(raw.strip().casefold())
