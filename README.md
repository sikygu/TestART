# TestART:  Improving LLM-based Unit Testing via Co-evolution of Automated Generation and Repair Iteration

TestART is an innovative coverage-driven automated unit testing framework that leverages Large Language Models (LLMs) to generate high-quality unit tests for Java code. The framework employs template-based code repair techniques and iterative feedback mechanisms to continuously improve test case quality and coverage.

## Key Features

- Template-based error correction for LLM-generated test cases
- Coverage-guided iterative test generation
- Automated test case refinement based on execution feedback
- Support for both branch and line coverage metrics

## Project Components

The repository contains:

- Frontend UI interface
- Backend service implementation
- Docker container for easy deployment
- Experimental results and datasets

## Architecture Overview

![System Architecture](https://github.com/user-attachments/assets/6db7490e-36d6-458e-a470-618f8e046428)

The workflow consists of the following key components:

1. Dataset parsing and method extraction (`utils/dataset.py`)
2. Task allocation (`allocator.py`)
3. Initial test suite generation (`tasks/unit_test.py`)
4. Test suite repair and iteration (`utils/fix.py`, `utils/iter.py`)

## Getting Started

### Prerequisites

#### Required Resources

Before starting, download the necessary files:

1. Docker Image:
   - [Download from Baidu Drive](https://pan.baidu.com/s/1IaFf4PswM2OmHQhx_jHM-Q?pwd=5ped)
   - Extraction code: 5ped
2. Dataset:
   - [Download from Figshare](https://figshare.com/s/a1b085fb84d684dc2d1c)

You can either run TestART locally or using Docker.

#### Local Setup

- Python 3.11
- Maven 3.9.6
- Java 8
- PostgreSQL 16
- Required Python dependencies

Configure Prefect:

```bash
prefect config set PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://postgres:yourPassWord@localhost:5432/prefect"
prefect config set PREFECT_API_URL="http://127.0.0.1:4200/api"
prefect config set PREFECT_UI_API_URL="http://127.0.0.1:4200/api"
```

Start Prefect server:

```bash
prefect server start
```

#### Docker Setup

1. Load the image:

```bash
docker load -i llmtest4j.tar
```

2. Run the container:

```bash
docker run -p 4200:4200 -p 5173:5173 -p 25734:25734 -e URL=${URL} -it llmtest4j:1.0
```

## Usage

### Dataset Upload

![Dataset Upload](https://github.com/user-attachments/assets/711d6e77-7bed-4105-9c71-6cb778b30107)


Access the web interface and upload your dataset through the Dataset menu.

### Running Tests

![Command Options](https://github.com/user-attachments/assets/e1d6419d-0d4e-4b6f-9b2b-bc92744cd600)

Execute tests using:

```bash
python main.py --api_key xxxxx --api_base http://xxx.xx/v1 --dataset_name dat --dataset_start_index 0 --dataset_end_index 1
```

### Monitoring Progress

![Task Monitoring](https://github.com/user-attachments/assets/96fdd35f-a5d8-4fb5-b2c1-6681c033fad4)

![Execution Details](https://github.com/user-attachments/assets/673e0f0a-721f-4e58-812c-52df287dfcbe)


### Viewing Results

![Results Dashboard](https://github.com/user-attachments/assets/3b38b52d-17e3-48b1-8914-4e50b17051f1)


Generated test files are saved in `~/GPT-Java-Tester/result`.

## Quality Assessment

We use PIT (Pitest) for mutation testing to evaluate test suite quality. Key metrics include:

- Test Strength: Ratio of killed mutations to covered mutations
- Mutation Coverage: Ratio of killed mutations to total mutations
- Line Coverage: Percentage of code lines covered by tests

Configuration includes:

- 4 threads for parallel execution
- DEFAULT mutators
- Custom filter for public methods
- HTML output format

## Notes

- Datasets can be single .java files or .zip archives with src/main/java structure
- Pre-generated test cases are available through our provided dataset link
- Use `--dataset_end_index 99999` to process all methods in a dataset
