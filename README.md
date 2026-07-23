# Qlik IA Development

## Overview

A comprehensive repository demonstrating how to leverage Artificial Intelligence and modern data engineering practices within Qlik Cloud. This project showcases complete data pipeline implementations using a medallion architecture, from data ingestion through analytics, with integration examples for VS Code and practical project templates.

## Contents

- [VS Code Integration Guide](guia-integracao-vscode-qlik-cloud-mcp.md) — Set up and configure VS Code with Qlik Cloud using MCP servers for seamless development.

### Examples

- [Example 1: Basic Sales Data Pipeline](./Qlik_IA_Example/README.md) — A foundational data engineering example using MySQL as source, implementing medallion architecture (landing, bronze, silver, gold layers) with data stored in Amazon S3 and analytics in Qlik Cloud.

- [Example 2: CDC-Based Advanced Pipeline](./Qlik_IA_Example2/README.md) — An extended data engineering implementation using Change Data Capture (CDC) for incremental data ingestion, handling complex transformations including consolidated fact tables, and establishing comprehensive development standards for enterprise-scale pipelines.
