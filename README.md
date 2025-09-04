# SmartVault API Development Setup

### Prerequisites

- Python3
- Basic familiarity with Backend Development

### Step 1: Clone this repository

```bash
  git clone https://github.com/99lash/smartvault-api.git
  cd smartvault-api
```

### Step 2: Create and Activate a python virtual environment

#### Step 2.1: Create virtual environment

```bash
  python3 -m venv .venv
```

#### Step 2.2 Activate virtual environment

**Linux / MacOS**

```bash
  source .venv/bin/activate
```

**Windows (Powershell)**

```bash
  .venv\Scripts\Activate
```

### Step 3: Upgrade pip (optional but recommended)

```bash
  pip install --upgrade pip
```

### Step 4: Install project dependencies `requirements.txt`

```bash
  pip install -r requirements.txt
```

### Step 5: Run the development server

```bash
  uvicorn app.main:app --reload
```

### Recommended vscode extension
- SQLite viewer (Florian Klampfer)

### ENV config
- choose only one DATABASE_URL and paste it inside the .env file
- QUESTION: where's the .env file?
- you gotta create it first, knee gas!

### End point testing
```bash
http://127.0.0.1:8000/docs
```