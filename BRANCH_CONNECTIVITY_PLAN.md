# 📌 Branch Connectivity & 2-Way Workflow Implementation Plan

## 📖 Project Background
- **Project Name**: Kokkalatty Tea Transfers Manager (Holmwood Tea Factory).
- **GitHub Repository**: [https://github.com/MOHAMEDFOUZHAN/KOKKALATTY-Transfers-manager-](https://github.com/MOHAMEDFOUZHAN/KOKKALATTY-Transfers-manager-)
- **Current Stack**: Python, Flask, SQLite3, Waitress, PyInstaller (Desktop `.exe`), PyWebView GUI.

---

## 🔄 The 2-Way Round-Trip Workflow

```
[ Branch 1 (Factory Site) ] -- (1. Send Raw/Bulk Product) --> [ Branch 2 (Processing/Warehouse) ]
            ^                                                              |
            |                                                    (2. Pack into Bags/Packets)
            |                                                              |
[ Branch 1 (Main Store) ] <--- (3. Receive Bagged Stock) ------------------+
```

### Operational Steps:
1. **Step 1 — Bulk Dispatch (Branch 1 ➔ Branch 2)**:
   - Branch 1 sends raw/bulk tea product to Branch 2.
   - Status: Outgoing Bulk Transfer (`SENT`).
2. **Step 2 — Processing & Bagging (at Branch 2)**:
   - Branch 2 receives the bulk shipment.
   - Branch 2 packs the bulk product into **Bags / Packets** (e.g., 1,000 KG Bulk ➔ 20 Bags of 50 KG each).
3. **Step 3 — Return Dispatch (Branch 2 ➔ Branch 1)**:
   - Branch 2 dispatches the packed bags **BACK to Branch 1**.
   - Status: Outgoing Bag Transfer (`SENT`).
4. **Step 4 — Final Receipt (at Branch 1)**:
   - Branch 1 receives the finished bagged product into main store inventory.
   - Status: Transfer Completed (`RECEIVED`).

---

## 🌐 Multi-Location Connectivity Architecture

Since Branch 1 and Branch 2 operate at separate physical locations across the internet, the software requires real-time data connectivity so entries at Location A immediately reflect at Location B:

### Selected Connectivity Strategy:
- **Central Online Sync / Cloud Database Backend**:
  - Centralized storage (e.g., PostgreSQL/MySQL on cloud or cloud REST API endpoint for `app.py`).
  - Both desktop executables (Branch 1 PC & Branch 2 PC) connect securely over HTTPS / TCP to read and write shared live data.
  - Offline fallback support (local caching in SQLite) so operations continue smoothly if the internet connection drops temporarily at the factory.

---

## 🛠️ Required Technical Changes (Phase 2 Roadmap)

### 1. Database Schema Extensions
- **Support 2-Way Dispatches**:
  - Add origin and destination tags (`source_branch`, `target_branch`) to `invoices` and `transfer_items`.
- **Bagging & Processing Log**:
  - Create table `bagging_conversions` (Track bulk input weight vs output bag counts and grades).

### 2. Application Logic & Routing (`app.py`)
- Enable Branch 2 to create outgoing transfer invoices directed back to Branch 1.
- Add API endpoints for bagging logs (`/api/branch2/bagging/save`).
- Add background database sync or cloud API synchronization routine.

### 3. UI / Template Enhancements
- **Branch 2 UI**: Add a **Bagging / Conversion Screen** and an **Outgoing Transfer Screen** (Branch 2 ➔ Branch 1).
- **Branch 1 UI**: Add an **Incoming Bagged Stock Receipt Screen**.

---
*Created on 07 August 2026 for Kokkalatty Tea Transfers Manager.*
