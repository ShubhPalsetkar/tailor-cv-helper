"""The list of skills Tailor knows about, and how to find them in text.

Each skill has a main name and other ways people write it. Add your own
freely: put the main name first, then the other spellings in lowercase.
"""

import re

SKILLS = {
    "Cloud and DevOps": {
        "AWS": ["amazon web services"], "Azure": ["microsoft azure"],
        "Google Cloud": ["gcp", "google cloud platform"], "EC2": [], "S3": ["amazon s3"],
        "Lambda": ["aws lambda"], "DynamoDB": [], "CloudFormation": [], "CloudWatch": [],
        "IAM": [], "VPC": [], "EKS": [], "ECS": [], "Docker": ["containers", "containerisation", "containerization"],
        "Kubernetes": ["k8s"], "Helm": [], "Terraform": [], "Ansible": [], "Puppet": [], "Chef": [],
        "Jenkins": [], "GitHub Actions": [], "GitLab CI": ["gitlab"], "Azure DevOps": [],
        "CI/CD": ["ci/cd", "ci cd", "continuous integration", "continuous delivery", "continuous deployment"],
        "Infrastructure as Code": ["iac", "infrastructure-as-code"], "Linux": ["unix", "ubuntu", "red hat", "rhel"],
        "Bash": ["shell scripting", "bash scripting"], "PowerShell": [], "Git": ["version control"],
        "Prometheus": [], "Grafana": [], "Datadog": [], "Splunk": [], "ELK": ["elasticsearch", "kibana", "logstash"],
        "Monitoring": ["observability", "alerting"], "Networking": ["tcp/ip", "dns", "load balancing"],
        "Serverless": [], "Microservices": [], "SRE": ["site reliability"], "Incident management": ["on-call", "on call"],
        "Nginx": [], "Apache": [],
    },
    "Programming": {
        "Python": [], "Java": [], "JavaScript": ["js"], "TypeScript": [], "C#": [".net", "dotnet"], "C++": [],
        "Go": ["golang"], "Rust": [], "Ruby": [], "PHP": [], "Kotlin": [], "Swift": [], "Scala": [],
        "SQL": ["t-sql", "pl/sql"], "R": ["r programming"], "HTML": ["html5"], "CSS": ["css3", "sass"],
        "React": ["react.js", "reactjs"], "Angular": [], "Vue": ["vue.js"], "Node.js": ["node", "nodejs"],
        "Django": [], "Flask": [], "FastAPI": [], "Spring": ["spring boot"], "REST APIs": ["rest", "restful", "api", "apis"],
        "GraphQL": [], "Object-oriented programming": ["oop", "object oriented"],
    },
    "Data and AI": {
        "Excel": ["microsoft excel", "spreadsheets", "vlookup", "pivot tables"], "Power BI": [], "Tableau": [],
        "Data analysis": ["data analytics", "analysing data", "analyzing data"], "Statistics": [],
        "Machine learning": ["ml"], "Deep learning": [], "AI": ["artificial intelligence", "llm", "llms", "generative ai"],
        "Pandas": [], "NumPy": [], "scikit-learn": ["sklearn"], "TensorFlow": [], "PyTorch": [],
        "PostgreSQL": ["postgres"], "MySQL": [], "MongoDB": [], "Redis": [], "Snowflake": [], "Spark": ["apache spark", "pyspark"],
        "ETL": ["data pipelines"], "Data visualisation": ["data visualization", "dashboards", "reporting"],
    },
    "Testing and quality": {
        "Test automation": ["automated testing", "automation testing"], "Selenium": [], "Cypress": [], "Playwright": [],
        "Unit testing": ["pytest", "junit"], "Quality assurance": ["qa", "quality engineering"],
        "Performance testing": ["load testing", "jmeter"],
    },
    "Security": {
        "Cyber security": ["cybersecurity", "information security", "infosec"], "Penetration testing": [],
        "Security compliance": ["iso 27001", "soc 2", "gdpr", "pci dss"], "Identity and access": ["sso", "oauth", "active directory"],
    },
    "Ways of working": {
        "Agile": ["scrum", "kanban", "sprints"], "Jira": ["confluence"], "Project management": ["managing projects"],
        "Stakeholder management": ["stakeholders"], "Change management": [], "Risk management": [],
        "Documentation": ["technical writing"], "Problem solving": ["troubleshooting", "problem-solving", "root cause"],
        "Communication": ["communication skills"], "Teamwork": ["team player", "collaboration", "collaborative"],
        "Leadership": ["leading teams", "team leadership", "line management", "people management", "managing a team"],
        "Mentoring": ["coaching"], "Time management": ["prioritisation", "prioritization", "organised", "organized"],
        "Attention to detail": ["detail-oriented", "detail oriented"], "Training": ["training staff", "onboarding"],
    },
    "Business and customers": {
        "Customer service": ["customer experience", "customer-facing", "customer facing", "customer care"],
        "Sales": ["selling", "upselling"], "Retail": ["store operations", "shop floor"],
        "Stock control": ["stock management", "inventory", "replenishment", "merchandising"],
        "Cash handling": ["tills", "cash management"], "Health and safety": ["h&s", "risk assessments"],
        "Budgeting": ["budgets", "p&l", "profit and loss", "forecasting"], "Account management": [],
        "Marketing": ["digital marketing", "seo", "social media"], "CRM": ["salesforce", "hubspot"],
        "Microsoft Office": ["ms office", "office 365", "microsoft 365", "word", "outlook", "powerpoint"],
        "Recruitment": ["hiring", "interviewing"], "Scheduling": ["rotas", "rostering"],
        "Logistics": ["supply chain", "warehouse"], "Process improvement": ["continuous improvement", "lean", "six sigma"],
    },
    "Qualifications": {
        "Degree": ["bachelor", "bachelor's", "bachelors", "bsc", "ba", "beng", "undergraduate degree"],
        "Master's degree": ["master's", "masters", "msc", "ma", "mba"], "PhD": ["doctorate"],
        "AWS certification": ["aws certified", "solutions architect associate", "aws solutions architect"],
        "Azure certification": ["az-900", "az-104", "azure certified"], "Kubernetes certification": ["cka", "ckad"],
        "PRINCE2": [], "ITIL": [], "CIPD": [], "ACCA": [], "CSCS": [],
        "Driving licence": ["driving license", "full uk driving licence", "clean driving licence"],
        "Security clearance": ["sc clearance", "dv clearance", "bpss"],
    },
}

# Words that are too common to count as a skill on their own in a CV.
_LOOSE = {"api", "apis", "rest", "node", "word", "ml", "ma", "ba", "qa", "js", "lean", "spring", "go", "r"}


def _pattern(alias: str) -> str:
    return r"(?<![A-Za-z0-9+#])" + re.escape(alias) + r"(?![A-Za-z0-9+#])"


_INDEX = []
for _cat, _items in SKILLS.items():
    for _name, _aliases in _items.items():
        forms = {_name.lower(), *[a.lower() for a in _aliases]}
        for form in forms:
            # Short or loose words must match with exact capitals, so "go" in
            # "go above and beyond" is not read as the Go language.
            exact = form in _LOOSE or len(form) <= 2
            if exact:
                shown = _name if form == _name.lower() else form.upper()
                _INDEX.append((_name, _cat, re.compile(_pattern(shown))))
            else:
                _INDEX.append((_name, _cat, re.compile(_pattern(form), re.I)))

CATEGORY = {name: cat for cat, items in SKILLS.items() for name in items}


def find_skills(text: str) -> dict:
    """Return {skill name: number of times it appears}."""
    found = {}
    for name, _cat, rx in _INDEX:
        n = len(rx.findall(text))
        if n:
            found[name] = found.get(name, 0) + n
    return found
