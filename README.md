# **🚀 Contributing to Bluntlyy**

Thank you for your interest in contributing to **Bluntlyy**! To keep this project organized, maintainable, and stable, please follow these guidelines.

---

## **🛠 Getting Started**


1. **Clone the repository** directly to your local machine:

```
git clone https://github.com/<your-username>/Bluntlyy.git
cd Bluntlyy
```

2. **Fetch the latest branches and checkout `dev`** (since it is ahead of `main`):

```
git fetch origin
git checkout dev
git pull origin dev
```

3. **Install dependencies:**

```
npm install
```

4. **Run the development server:**

```
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to see your changes.

5. **Create a branch** for your feature or bug fix from `dev`:

```
git checkout -b feature/your-feature-name
```

---

## **🐛 Creating Issues**

- **One issue per task**.  
- **Title format:**
  - `Feature: Add login page`  
  - `Bug: Fix navbar dropdown on mobile`  
- **Include in the description:**
  - **Summary:** What needs to be done  
  - **Steps to Reproduce** (for bugs)  
  - **Expected Behavior**  
  - **Additional Context:** screenshots, code snippets, references  
- **Assign a milestone** and **labels** (`frontend`, `backend`, `feature`, `bug`, `priority-high`).

---

## **💻 Working on Issues**

1. **Assign yourself** to the issue.  
2. **Create a branch** based on the issue from `dev`:

```
git checkout -b issue-#<issue-number>-short-description
```

3. **Make your changes and commit frequently:**

```
git commit -m "Fix: Correct navbar dropdown on mobile"
```

4. **Push your branch to the repository:**

```
git push origin issue-#<issue-number>-short-description
```

---

## **🔀 Pull Request Workflow (Dev First)**

All changes go to **`dev`** first before merging into `main`.

1. **Open a Pull Request (PR) against the `dev` branch**, not `main`.  
2. **Link your PR to the relevant issue**, e.g., `Closes #12`.  
3. Include a **clear description** of your changes.  
4. Ensure your code passes **linting and tests:**

```
npm run lint
npm run test
```

5. Once approved and tested in `dev`, the PR will be merged into `main` for production.

**📌 Branch Summary:**

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code |
| `dev`  | Integration/testing branch |
| `feature/xyz` or `issue-#` | Individual work branches |

---

## **🧹 Code Standards**

- **Formatting:** Use **Prettier** for consistent style.  
- **Linting:** Follow **ESLint rules** (`npm run lint`).  
- **Components:** Keep components **small, reusable, and documented**.  
- **Naming:** Use **clear, descriptive names** for variables, functions, and files.

---

## **📅 Milestones & Project Board**

- **Monthly Milestones:** Group issues by month/sprint (e.g., `November 2025`).  
- **Labels:** Categorize issues (`frontend`, `backend`, `feature`, `bug`).  
- **Project Board:** Track progress using **To Do → In Progress → Done**.

---

## **🙏 Thank You**

Your contributions improve **Bluntlyy** for everyone! Thank you for your time, effort, and collaboration. 🚀
