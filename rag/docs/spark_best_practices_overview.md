# Fabric Spark Best Practices Overview

This series of articles outlines best practices for optimizing the performance, security, and cost of Spark jobs when running Spark Notebooks and Spark Job Definitions (SJDs) on Microsoft Fabric.

## Articles in this Series

- **Fabric Spark Capacity and Cluster Planning**: Guidelines for Sizing
- **Fabric Spark Security**
- **Development and Monitoring**
- **Spark Basics** - If you're new to Spark, start here

## Common Acronyms

| Acronym | Full Term |
|---------|-----------|
| AKV | Azure Key Vault |
| AQE | Adaptive Query Execution |
| CDC | Change Data Capture |
| CU | Capacity Unit |
| DAG | Directed Acyclic Graph |
| HC | High Concurrency |
| JVM | Java Virtual Machine |
| MLV | Materialized Lake View |
| MPE | Managed Private Endpoint |
| NEE | Native Execution Engine |
| OOM | Out of Memory |
| PL | Private Link |
| ORC | Optimized Row Columnar |
| RDD | Resilient Distributed Dataset |
| SJDs | Spark Job Definitions |
| SPN | Service Principal Name |
| SRE | Site Reliability Engineer |
| UDF | User Defined Function |
| UI | User Interface |
| VM | Virtual Machine |
| VNet | Virtual Network |
| WS OAP | Workspace Outbound Access Protection |

## Prerequisites

You should be familiar with basic data engineering concepts in Fabric. If you're new to Fabric, refer to the Fabric data engineering documentation.

## Key Focus Areas

1. **Performance Optimization** - Maximize Spark job efficiency
2. **Security** - Protect your data and workloads
3. **Cost Management** - Optimize capacity usage
4. **Monitoring** - Track and troubleshoot Spark jobs
