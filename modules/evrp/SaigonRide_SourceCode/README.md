# SaigonRide: Distributed Vehicle Rental System
**Course:** Software Engineering | Ton Duc Thang University  
**Team:** Saigon Ride Team | **Chosen Tier:** Tier 4 (Highest Tier)  

---

## 🚀 Deployed URLs & Repository Info
* **GitHub Repository Link:** [https://github.com/Thundercok/SaigonRide](https://github.com/Thundercok/SaigonRide) *(Contains >30 commits per team member)*
* **Live Cloud URL:** [https://saigonride-production-0749.up.railway.app/](https://saigonride-production-0749.up.railway.app/) *(Deployed live on Railway)*
* **Video Demo Link:** *[Insert your unlisted YouTube or Google Drive link here]* *(End-to-end walkthrough of all use cases, maximum 20 minutes)*

---

## 🛠️ Project Tier & Technical Stack
This project is built under **Tier 4** (the most advanced tier, allowing a maximum raw score of **10.0/10.0**):
* **Web & Backend Framework:** ASP.NET Core MVC (Code-First) on **.NET 10.0**
* **Database:** PostgreSQL (Production on Railway, local fallback via TimescaleDB Docker container)
* **Real-time Synchronization:** ASP.NET Core SignalR (live sync for kiosk status & admin dashboard)
* **Payment Integrations (Strategy Design Pattern):**
  * Local Bank Transfer: **SePay API Webhooks** sandbox (VietQR code auto-generation + countdown timers)
  * International Credit Card: **Stripe Checkout API** + Webhook events
* **2FA Security Subsystem:** Time-based One-Time Passwords (TOTP) using standard Base32 secrets (OTPauth)
* **Automated Testing:** Integration, unit, and end-to-end UI tests written using **Microsoft Playwright** and **NUnit**

---

## 🔑 Seeded Credentials & Logins
The database is auto-seeded upon first execution. Use the credentials below to log into each role:

| Interface | Username / Email | Password / OTP | Key Notes |
| :--- | :--- | :--- | :--- |
| **Admin Dashboard** | `admin@saigonride.com` | `Admin@SaigonRide99!` | Full visibility into stations, vehicles, and real-time revenue analytics. |
| **Rider Web / Mobile** | `test@saigonride.com` | `Test@SaigonRide99!` | Pre-seeded with a **500,000 VND** RideCard balance for renting. |
| **TOTP / 2FA Account** | `totp_test@saigonride.com` | Password: `Test@1234567!` <br>TOTP Secret: `JBSWY3DPEHPK3PXP` | Used for E2E UI testing of the Time-based One-time Password authentication flow. |
| **Kiosk Service Account** | `kiosk@saigonride.com` | `Kiosk@Internal99!` | Backend authentication service account for kiosk instances. |

---

## 💻 Local Setup & Execution Guide

### 1. Prerequisites
Make sure you have the following installed on your machine:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for running PostgreSQL locally)
* [.NET 10.0 SDK](https://dotnet.microsoft.com/en-us/download/dotnet/10.0)

### 2. Configure Local Database
1. Spin up the local database container if not already running.
2. Create the `saigonride` database using PostgreSQL command-line tools:
   ```bash
   docker exec nckh-traffic-camera-db-1 psql -U trafficflow -d trafficflow -c "CREATE DATABASE saigonride;"
   ```
3. Set the connection string in your user secrets store to prevent credentials from being committed to version control:
   ```bash
   cd Sprint4/SaigonRide.App
   dotnet user-secrets set "ConnectionStrings:DefaultConnection" "Host=localhost;Port=5432;Database=saigonride;Username=trafficflow;Password=trafficpass123"
   ```

### 3. Apply Migrations & Seed
Run Entity Framework migrations to prepare your database tables locally:
```bash
dotnet ef database update
```
*(Seeding logic runs automatically on application startup, resetting and seeding testing configurations securely).*

### 4. Run the Web Server
Start the ASP.NET Core application:
```bash
dotnet run
```
The server will start listening at: **`http://localhost:5297`**

---

## 🧪 Running Automated Tests

We have written a comprehensive suite of automated unit and end-to-end integration tests.

### Run NUnit Unit Tests
Tests for the `PricingEngine` and mock payment verification layers:
```bash
dotnet test Sprint4/SaigonRide.Tests/SaigonRide.Tests.csproj
```

### Run Playwright E2E UI Tests
To execute the UI flows including registration, kiosk login, vehicle selection, active rentals, top-ups, Stripe redirects, and return receipt workflows:
1. Ensure the web application is running locally at `http://localhost:5297`.
2. Run the Playwright integration tests:
   ```bash
   dotnet test Sprint4/SaigonRide.UITests/SaigonRide.UITests.csproj
   ```
   *(Playwright tests will automatically use a mock OTP bypass `123456` or generate dynamic TOTP codes using the seeded base32 secret `JBSWY3DPEHPK3PXP` via `OtpNet` library).*
