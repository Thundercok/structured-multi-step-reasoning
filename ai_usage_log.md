# SaigonRide: Generative AI Usage Log (Appendix)
**Course:** Software Engineering | **Semester:** 2, 2025-2026  
**Team:** Saigon Ride Team | **Chosen Tier:** Tier 4  

This log details the usage of Generative AI tools (including Google DeepMind's Antigravity assistant) in the design, debugging, and testing phases of the SaigonRide project.

---

| Date | Tool / Assistant | User Prompt (Search / Request) | Assistant Output / Action taken | Rationale / Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **May 12, 2026** | Gemini Assistant | `grep -rn "class SePayWebhookPayload" SaigonRide.App/` | Identified duplicate definition of `SePayWebhookPayload` class in `WalletDtos.cs` and `SePayWebhookPayload.cs`. | Removed duplicate record definition in `WalletDtos.cs` to resolve compiler error CS0101. |
| **May 12, 2026** | Gemini Assistant | `Views/Wallet/Index.cshtml(6,37): error CS8133: Cannot deconstruct dynamic objects.` | Recommended explicit casting: `((string, string))ViewBag.Flash` to unbox the tuple from the dynamic ViewBag object. | Resolved compilation errors CS8133 and CS0019 in the Razor wallet view. |
| **May 12, 2026** | Gemini Assistant | `dotnet ef database update failed — bad connection string (Format of the initialization string does not conform...)` | Identified that `appsettings.Development.json` was overriding User Secrets with the literal placeholder `YOUR_RAILWAY_POSTGRES_URL`. | Advised deleting the `ConnectionStrings` block from `appsettings.Development.json` to allow correct configuration load order. |
| **May 13, 2026** | Gemini Assistant | `Draft a clean, robust Playwright integration test suite covering Kiosk login, vehicles, and returns.` | Provided a structured NUnit C# test file `KioskFlowTests.cs` using environment variables for base URLs and credentials. | Standardized the Playwright integration tests and enabled them to run locally and against Railway. |
| **May 31, 2026** | Antigravity AI Coding Assistant | `dotnet ef database update hitting localhost:5432 and ignoring User Secrets` | Identified that `AppDbContextFactory.cs` was not configured with `.AddUserSecrets<AppDbContextFactory>()` at design-time. | Added the `.AddUserSecrets` call to the configuration builder inside the DbContext factory to fix EF CLI tool connections. |
| **May 31, 2026** | Antigravity AI Coding Assistant | `Create a completed self-assessment grading rubric and draft submission packages` | Generated the self-assessment report markdown template and packaged the repository as `SaigonRide_SourceCode.zip`. | Automated packaging and administrative document generation for final grading. |

---

## 📝 Declared Guidelines
* **Code Implementation:** All core business logic, entity design, SignalR hubs, and payment gateway strategic logic were written and refined by the team members. AI was used as a pair-programmer to troubleshoot compile-time errors, design EF migration factories, and generate robust unit/integration tests.
* **Academic Integrity:** No proprietary codebase or intellectual property was violated. All external sandbox payment resources (Stripe/SePay webhooks) are safe mock environments.
