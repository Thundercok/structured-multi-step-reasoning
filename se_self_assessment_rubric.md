# Saigon Ride - Final Project Grading Rubric
**Course:** Software Engineering | **Semester:** 2, 2025-2026  
**Team:** Saigon Ride Team | **Chosen Tier:** Tier 4 | **Assessor:** Ky-Trung Pham  

## Team Information
| Student ID | Student Full Name | % Contribution (X+Y=100%) |
| :--- | :--- | :--- |
| **523c0012** | Huynh Nhat Huy | 50% (X) |
| **523v0002** | Bui Quang Huy | 50% (Y) |

---

## Step 1: Technology Tier Cap Rules
* **Tier 4 (Max 10.0/10):** Tier 3 + Live External API + Adv. Admin Dashboard + Automation Tests. *(Our group meets all criteria for Tier 4).*

---

## Step 2: Assessment Criteria

### Part 1: Project Proposal & Requirements Engineering (20%)
| Criteria | Max % | Self | Earned | Notes / Feedback |
| :--- | :---: | :---: | :---: | :--- |
| **Formatting:** Title page includes Project Name, Team, IDs, and Tier. | 1% | 1% | | Title page fully formatted on page 1 of the report. |
| **Problem Statement & Roles:** Clear client summary, chosen SDLC methodology, and explicit role breakdown. | 2% | 2% | | Scrum methodology utilized. Roles clearly divided: Nhat Huy (Backend/DB/Payment Architect) & Quang Huy (Frontend/QA/E2E UI Testing). |
| **Use Case Ownership:** Explicitly assigns at least 1 core Use Case per student. Ensures each assigned UC involves complete CRUD operations. | 4% | 4% | | Nhat Huy: Rental Reservation & Wallet CRUD workflows. <br>Quang Huy: Station/Vehicle CRUD & Return workflows. |
| **Functional Requirements (FRs):** Bulleted list ("The system shall..."). Clearly maps to the chosen Use Cases AND the 2 required reports. | 4% | 4% | | Bulleted list of FRs mapping directly to rental use cases and reports (Station Utilisation, Fleet/Revenue report). |
| **Quality Attributes (NFRs):** Defines at least 3 specific, measurable non-functional requirements (e.g., Performance, Security, Usability). | 4% | 4% | | Measurable NFRs defined for security (TOTP 2FA), transaction latency (<2s), and layout responsiveness. |
| **Solution Pitch:** 5-7 minutes. Clear explanation of the solution. All members speak and explicitly claim ownership of their assigned Use Case. | 5% | 5% | | Solution pitch presentation completed successfully with active participation. |
| **PART 1 TOTAL** | **20%** | **20%** | | |

---

### Part 2: Software Design, Architecture & UI/UX (25%)
| Criteria | Max % | Self | Earned | Notes / Feedback |
| :--- | :---: | :---: | :---: | :--- |
| **Use Case & Specs:** Overall UC Diagram showing boundaries/actors. Detailed UC Specs (Main/Alt flows, Pre/Post conditions) for assigned UCs. | 4% | 4% | | Use Case diagram covers Kiosk, Admin, and Mobile interfaces. Specifications detailed. |
| **Behavioral Diagrams:** UML Sequence or Activity Diagram specific to each student's chosen Use Case. | 3% | 3% | | Custom Sequence Diagrams provided for Start Rental, End Rental, and TOTP verification workflows. |
| **Structural Design:** CRC cards present. Formal UML Class Diagram (or ERD) logically mapped out. | 4% | 4% | | Complete UML class diagram and CRC cards mapped to the Code-First DB model. |
| **Architecture & Quality:** Visualizes MVC/3-Tier setup. Briefly explains how design incorporates Quality Design (SOLID, cohesion/coupling) to meet NFRs. | 4% | 4% | | Visual MVC architecture. Clean SOLID strategy pattern used for Payments (Stripe/VietQR Strategy). |
| **UI/UX Prototype:** Figma link provided. Web tiers use responsive grid/Bootstrap. UI reflects multi-payment options, categories, and reports. | 5% | 5% | | Figma interactive link provided; designs match the final implemented web bootstrap UI grid. |
| **Design Review:** 7-10 minutes. Effective technical walkthrough of CRC cards, database logic, and the Figma prototype. | 5% | 5% | | Design review presentation successfully presented. |
| **PART 2 TOTAL** | **25%** | **25%** | | |

---

### Part 3: Implementation, Testing & Product Demo (35%)
| Criteria | Max % | Self | Earned | Notes / Feedback |
| :--- | :---: | :---: | :---: | :--- |
| **Version Control:** GitHub repo linked. >10 meaningful commits per student to prove equitable work. | 4% | 4% | | GitHub repository linked; commits verified (>30 meaningful commits per student). |
| **Source Code / Architecture:** Strict MVC/3-Tier separation. Complete CRUD for chosen use cases. Bootstrap used (for Web Tiers). | 8% | 8% | | Clear separation of Model, View, Controller, and Services. Full CRUD for fleet management and rentals. |
| **Detailed Design Justification:** Explains final implemented design. Explicitly compares to Part 2 design and justifies any logic/database changes made. | 4% | 4% | | Section details TPH transition for Identity user management and Strategy pattern for payments. |
| **QA - Test Plan & Execution:** Clear Test Cases table. Execution evidence (screenshots of passed Unit Tests). | 5% | 5% | | Detailed test plans with NUnit tests (`SaigonRide.Tests`) and Playwright tests (`SaigonRide.UITests`). |
| **QA - EP & BVA Logic:** Explicitly shows use of Equivalence Partitioning & Boundary Value Analysis to test the 15% discount logic. | 5% | 5% | | Formally documented EP & BVA testing tables for reservation deposits and minimum card balances. |
| **Verification (Traceability):** RTM or Summary proving the final software meets the original FRs and NFRs from Part 1. | 4% | 4% | | Requirements Traceability Matrix (RTM) fully maps FRs/NFRs to tests. |
| **(Tier 4 Only):** Source code/logs for Automation Tests, live external API, advanced Dashboard, and Live Cloud URL. | Req for 10 | Met | | Automation logs (41 Playwright tests passed), Stripe/SePay webhook APIs, Live URL on Railway, and real-time dashboard. |
| **Execution & Q&A:** 10-15 minutes. Flawless live execution of chosen UCs. Showcases 2 live reports. Handles audience Q&A successfully. | 5% | 5% | | Live demo performed successfully. |
| **PART 3 TOTAL** | **35%** | **35%** | | |

---

### Final Submission: Comprehensive Report & Video Demo (20%)
| Criteria | Max % | Self | Earned | Notes / Feedback |
| :--- | :---: | :---: | :---: | :--- |
| **Formatting:** Parts 1, 2, and 3 combined into a single, polished PDF with bookmarks. | 2% | 2% | | Polished PDF report generated. |
| **Feedback Implementation:** Evidence that previous instructor feedback from presentations was addressed in the final document. | 4% | 4% | | Addressed previous feedback regarding Stripe webhook handlers and Kiosk flow validation. |
| **Lessons Learnt:** Dedicated section where each team member reflects on their SDLC journey, challenges, and resolutions. | 4% | 4% | | Personal reflection sections included for both Nhat Huy and Quang Huy. |
| **Video Demo:** End-to-End Showcase. High-quality .mp4 or unlisted YouTube link. Showcases all UCs and reports working end-to-end with clear audio/narration. | 10% | 10% | | 10-minute HD walkthrough video provided showing all admin, user, and kiosk flows. |
| **FINAL TOTAL** | **20%** | **20%** | | |

---

## Step 3: Bonus Opportunities
| Bonus Criteria | Reward | Self | Earned | Notes / Feedback |
| :--- | :--- | :---: | :---: | :--- |
| **Web Tier Cloud Deployment (Tiers 1B, 2, 3 only):** Successfully hosting the final web application on a live cloud platform (Azure, Render, Heroku). | +0.5 to +1.0 | **N/A** | | Not applicable (our chosen tier is Tier 4, which already requires live deployment). |

---

## Final Grade Calculation

| Category | Your group (Self-Assess) | Instructor (Mark) |
| :--- | :---: | :---: |
| **Raw Score (Sum of all Parts)** | **100% / 100%** | **_______ / 100%** |
| **Apply Tier Cap (See Step 1)** | **10.0 / 10.0** | **_______ / 10.0** |
