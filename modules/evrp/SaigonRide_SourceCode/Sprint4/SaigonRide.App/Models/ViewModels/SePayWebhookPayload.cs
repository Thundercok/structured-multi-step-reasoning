namespace SaigonRide.App.Models.ViewModels
{
    public class SePayWebhookPayload
    {
        public int id { get; set; }
        public string gateway { get; set; } = string.Empty;
        public string transactionDate { get; set; } = string.Empty;
        public string accountNumber { get; set; } = string.Empty;
        public string? subAccount { get; set; }
        public string content { get; set; } = string.Empty; // Chứa mã đơn hàng (ví dụ: SGR 6)
        public string transferType { get; set; } = string.Empty; // "in" là tiền vào, "out" là tiền ra
        public decimal transferAmount { get; set; }
        public decimal accumulated { get; set; }
        public string referenceCode { get; set; } = string.Empty;
        public string description { get; set; } = string.Empty;
    }
}