# 🛒 Store POS System

A lightweight **Point-of-Sale (POS)** desktop application built with Python's Tkinter and SQLite. It helps small businesses manage products, process sales, track transactions, and generate insights—all without external dependencies.

![Screenshot](screenshot.png)  <!-- Replace with your actual screenshot -->

---

## ✨ Features

- **Product Management** – Add, edit, or delete products (name, price, stock).
- **Shopping Cart** – Add items, adjust quantities, remove, or clear the cart.
- **Process Sales** – Record a sale, automatically deduct stock, and save the transaction with timestamp.
- **Transaction History** – View all past sales with date, total, and item-level details.
- **Sales Reports & Analytics**:
  - Summary (total sales, number of transactions, average sale) over any date range.
  - Daily breakdown of sales.
  - Top‑selling products (by quantity and revenue).
  - Low‑stock alerts with configurable threshold.
- **Export Reports** – Export the current report to a CSV file.
- **Pre‑loaded Sample Data** – Get started immediately with demo products (Apple, Banana, Bread, etc.).

---

## 📦 Requirements

- Python 3.6+
- Tkinter (usually included with Python)
- SQLite3 (built‑in)

No third‑party packages are needed – only the Python standard library.

---

## 🚀 Installation & Running

1. **Clone the repository** (or download `pos.py`):
   ```bash
   git clone https://github.com/yourusername/store-pos-system.git
   cd store-pos-system
