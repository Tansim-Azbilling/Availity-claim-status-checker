# 🏥 Availity Claim Status Checker

> **Automated claim status verification tool for Healthcare Revenue Cycle Management**

A powerful Python automation tool that streamlines the process of checking insurance claim statuses on the Availity portal. Built for RCM professionals to eliminate hours of manual data entry and claim lookups.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [CSV Format](#-csv-format)
- [Output Format](#-output-format)
- [Workflow](#-workflow)
- [Troubleshooting](#-troubleshooting)
- [Building EXE](#-building-exe)
- [Tech Stack](#-tech-stack)
- [Contributing](#-contributing)

---

## 🎯 Overview

This tool automates the tedious process of checking claim statuses on Availity by:

- 📂 Reading patient/claim data from CSV files
- 🌐 Connecting to an existing Chrome browser session via CDP
- 🔍 Searching claims for multiple patients automatically
- 📊 Extracting comprehensive claim details (status, amounts, denial codes)
- 💾 Saving results back to CSV with detailed information
- 🔄 Handling multiple claims per patient and date ranges

**Use Case:** Perfect for RCM teams processing hundreds of claims daily who need to verify claim status, extract payment information, and identify denial reasons.

---

## ✨ Features

### Core Functionality
- ✅ **Batch Processing** - Process multiple claims in configurable batch sizes
- ✅ **Multi-Claim Support** - Handles multiple matching claims per invoice
- ✅ **Smart Date Matching** - Auto-normalizes date formats (`1/1/2026` ↔ `01/01/2026`)
- ✅ **Denial Code Extraction** - Automatically extracts and decodes denial reasons
- ✅ **Progress Tracking** - Saves progress after each row (resume on failure)
- ✅ **Real-time Logging** - GUI displays color-coded progress logs

### Reliability Features
- 🔄 **Auto-retry Logic** - Retries failed navigations with exponential backoff
- 🛡️ **Error Recovery** - Graceful degradation on individual row failures
- 📸 **State Recovery** - Reloads page between rows to prevent stuck states
- 💾 **Auto-save** - Saves progress after every processed row
- ⚡ **Connection Resilience** - Handles browser connection issues

### User Experience
- 🎨 **Clean GUI** - Tkinter-based interface with intuitive controls
- 📊 **Visual Feedback** - Color-coded logs (info/success/error)
- ⏸️ **Stop Anytime** - Graceful stop without losing progress
- 📁 **File Browser** - Easy CSV and output folder selection
- 🏥 **Multi-Payer** - Support for Healthfirst, Anthem, SWHNY (extensible)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GUI Layer (Tkinter)                  │
│  • File Selection  • Progress Display  • Controls       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  Threading Layer                        │
│         (Background processing for non-blocking UI)     │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                Business Logic Layer                     │
│  • CSV Processing  • Claim Logic  • Data Aggregation    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│             Web Scraping Layer (Playwright)             │
│  • Navigation  • Form Filling  • Data Extraction        │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              Browser (Chrome via CDP)                   │
│         (Manually authenticated user session)           │
└─────────────────────────────────────────────────────────┘
```

### Module Structure

```
📦 availity-claim-automation/
├── 📄 main.py                  # Entry point with all modules
│   ├── 🔧 Date Utilities       # Date format normalization
│   ├── 🌐 Browser Management   # CDP connection handling
│   ├── 📁 File Operations      # CSV read/write
│   ├── 🎯 Web Scraping         # Playwright automation
│   ├── ⚙️ Claim Processing     # Business logic
│   ├── 🔄 Batch Processing     # Orchestration
│   └── 🖼️ GUI Layer            # Tkinter interface
├── 📂 input/                   # CSV input files
├── 📂 output/                  # Generated reports
└── 📄 README.md                # This file
```

---

## 📋 Prerequisites

### System Requirements
- 🪟 **OS:** Windows 10/11 (recommended) or macOS/Linux
- 🐍 **Python:** 3.8 or higher
- 💾 **RAM:** Minimum 4GB (8GB recommended)
- 🌐 **Browser:** Google Chrome (latest version)

### Required Knowledge
- Basic command line usage
- Understanding of CSV files
- Familiarity with Availity portal

### Required Access
- 🔐 Valid Availity portal credentials
- 🏥 Access to claim status checker for your payer
- 📋 Patient data in proper CSV format

---

## 🚀 Installation

### Step 1: Clone or Download

```bash
git clone <your-repo-url>
cd availity-claim-automation
```

### Step 2: Install Python Dependencies

```bash
pip install playwright pandas
```

### Step 3: Install Playwright Browsers

```bash
playwright install chromium
```

### Step 4: Setup Chrome with Remote Debugging


[⬆ Back to Top](#-availity-claim-status-checker)

</div>
