# TestART: Automated Unit Test Generation with LLM

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

![System Architecture](https://cdn.nlark.com/yuque/0/2024/jpeg/46067456/1729587224496-1a9b0fa9-bda9-4ef0-832f-d294cb92b0e7.jpeg)

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

![Dataset Upload](https://cdn.nlark.com/yuque/0/2024/png/46067456/1729596829237-1fd4d9e8-eea5-4073-a1e4-38c9962950aa.png)

Access the web interface and upload your dataset through the Dataset menu.

### Running Tests

![Command Options](https://cdn.nlark.com/yuque/0/2024/png/46067456/1729584960101-1ba65762-d640-4422-8a42-d24c6ec07919.png)

Execute tests using:

```bash
python main.py --api_key xxxxx --api_base http://xxx.xx/v1 --dataset_name dat --dataset_start_index 0 --dataset_end_index 1
```

### Monitoring Progress

![Task Monitoring](https://cdn.nlark.com/yuque/0/2024/png/46067456/1729584994479-4137379f-caff-4c2b-bcc0-f9394a4d704e.png)
![Execution Details](https://cdn.nlark.com/yuque/0/2024/png/46067456/1729585469937-342b32f6-ca82-4db9-8368-82e2c196a903.png)

### Viewing Results

![Results Dashboard](https://cdn.nlark.com/yuque/0/2024/png/46067456/1729585385917-5514f2d9-0d13-45e2-9b6e-0fd36313ca75.png)

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
