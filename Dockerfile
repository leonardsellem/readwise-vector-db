# Stage 1: Builder
FROM python:3.12-slim AS builder

# Install poetry
RUN pip install poetry

# Set up a non-root user
RUN useradd --create-home appuser
WORKDIR /home/appuser

# Copy dependency definition files
COPY pyproject.toml poetry.lock ./

# Install dependencies into a virtual environment
RUN poetry config virtualenvs.in-project true && \
    poetry install --without=dev --no-root --no-interaction --no-ansi

# Copy the application source code
COPY . .

# Stage 2: Final image
FROM python:3.12-slim

# Set up a non-root user
RUN useradd --create-home appuser
USER appuser
WORKDIR /home/appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /home/appuser/.venv ./.venv

# Copy the application source code from the builder stage
COPY --from=builder /home/appuser/readwise_vector_db ./readwise_vector_db

# Set the PATH to include the virtual environment's binaries
ENV PATH="/home/appuser/.venv/bin:$PATH"

# Expose the port the app runs on
EXPOSE 8000

# The command to run the application will be specified in docker-compose.yaml
