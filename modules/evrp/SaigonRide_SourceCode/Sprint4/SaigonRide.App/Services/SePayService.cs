using System.Web;
using Microsoft.Extensions.Configuration;

namespace SaigonRide.App.Services
{
    public class SepayService
    {
        private readonly IConfiguration _config;

        public SepayService(IConfiguration config)
        {
            _config = config;
        }

        // Hàm này sinh ra đường link ảnh QR Code
        public string GenerateQrUrl(decimal amount, int rentalId)
        {
            string bankId = _config["Sepay:BankId"] ?? "bidv"; 
            string accountNumber = _config["Sepay:AccountNumber"] 
                                   ?? throw new InvalidOperationException("Missing Sepay:AccountNumber configuration.");
            string accountName = _config["Sepay:AccountName"] ?? "SAIGONRIDE"; 
            string template = _config["Sepay:Template"] ?? "compact2";
            
            // Nội dung chuyển khoản BẮT BUỘC phải map với Webhook (Ví dụ: "SGR 9")
            string content = $"SGR {rentalId}";

            // Encode dữ liệu để đảm bảo an toàn khi truyền qua URL (tránh lỗi khoảng trắng, dấu tiếng Việt)
            string encodedContent = HttpUtility.UrlEncode(content);
            string encodedName = HttpUtility.UrlEncode(accountName);

            // Ráp thành URL hoàn chỉnh của API VietQR
            string qrUrl = $"https://img.vietqr.io/image/{bankId}-{accountNumber}-{template}.png?amount={(long)amount}&addInfo={encodedContent}&accountName={encodedName}";

            return qrUrl;
        }

        public string GenerateWalletTopUpQrUrl(decimal amount, int transactionId)
        {
            string bankId = _config["Sepay:BankId"] ?? "bidv";
            string accountNumber = _config["Sepay:AccountNumber"]
                                   ?? throw new InvalidOperationException("Missing Sepay:AccountNumber configuration.");
            string accountName = _config["Sepay:AccountName"] ?? "SAIGONRIDE";
            string template = _config["Sepay:Template"] ?? "compact2";
            string content = $"SGRW {transactionId}";

            string encodedContent = HttpUtility.UrlEncode(content);
            string encodedName = HttpUtility.UrlEncode(accountName);

            return $"https://img.vietqr.io/image/{bankId}-{accountNumber}-{template}.png?amount={(long)amount}&addInfo={encodedContent}&accountName={encodedName}";
        }
    }
}
