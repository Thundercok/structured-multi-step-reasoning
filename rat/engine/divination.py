"""
rat.engine.divination — Lightweight, standalone divination tools:
1. Kinh Dịch (I Ching): 64 hexagrams, yin/yang lines, changing lines, interpretation.
2. Lenormand: 36 traditional oracle cards, 3-card spread (Past - Present - Future).
Zero external dependencies; pure Python.
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional, Tuple

# 8 Bát Quái: (name, symbol, binary 3 bits bottom-to-top where 1 is Yang, 0 is Yin)
TRIGRAMS = {
    (1, 1, 1): ("Càn", "☰", "Trời", "Mạnh mẽ, sáng tạo, khởi đầu"),
    (0, 1, 1): ("Đoài", "☱", "Đầm", "Vui vẻ, hòa nhã, thu hút"),
    (1, 0, 1): ("Ly", "☲", "Lửa", "Sáng suốt, văn minh, bám tựa"),
    (0, 0, 1): ("Chấn", "☳", "Sấm", "Hành động, chấn động, thức tỉnh"),
    (1, 1, 0): ("Tốn", "☴", "Gió", "Thuận phục, thấu suốt, khiêm nhu"),
    (0, 1, 0): ("Khảm", "☵", "Nước", "Hiểm trở, thận trọng, trí tuệ"),
    (1, 0, 0): ("Cấn", "☶", "Núi", "Ngăn chặn, tĩnh lặng, dừng lại"),
    (0, 0, 0): ("Khôn", "☷", "Đất", "Nhu thuận, bao dung, thành toàn"),
}

# 64 Quẻ Kinh Dịch: (Upper, Lower) -> (Tên quẻ, Ý nghĩa tổng quát, Lời khuyên của Chuột)
HEXAGRAMS_64: Dict[Tuple[str, str], Tuple[str, str, str]] = {
    ("Càn", "Càn"): ("Thuần Càn", "Vạn sự hanh thông, long khởi vũ vân", "Thời cơ lớn, giữ vững chính đạo và sự tự chủ."),
    ("Khôn", "Khôn"): ("Thuần Khôn", "Đức dày chở vật, nhu thuận đại cát", "Lắng nghe, kiên nhẫn tích lũy, chớ vội đứng đầu."),
    ("Khảm", "Chấn"): ("Thủy Lôi Truân", "Vạn sự khởi đầu nan, mầm non đội đất", "Gặp khó bước đầu là tự nhiên, cần định tâm và tìm trợ lực."),
    ("Cấn", "Khảm"): ("Sơn Thủy Mông", "Khai mở mông muội, học hỏi tiến bước", "Chân thành cầu học, chớ kiêu căng tự mãn."),
    ("Khảm", "Càn"): ("Thủy Thiên Nhu", "Chờ thời hành động, mây tụ thành mưa", "Kiên nhẫn chờ thời điểm chín muồi, ăn uống vui tươi."),
    ("Càn", "Khảm"): ("Thiên Thủy Tụng", "Bất hòa tranh chấp, thận trọng lùi bước", "Tránh kiện tụng tranh chấp, dừng lại đúng lúc thì an."),
    ("Khôn", "Khảm"): ("Địa Thủy Sư", "Hành quân dụng chúng, kỷ luật nghiêm minh", "Cần kỷ luật thép và người lãnh đạo công tâm."),
    ("Khảm", "Khôn"): ("Thủy Địa Tỷ", "Gắn kết thân thiện, tìm người đồng chí", "Tìm kiếm sự liên minh, giúp đỡ chân thành."),
    ("Tốn", "Càn"): ("Phong Thiên Tiểu Súc", "Tích lũy nhỏ bé, gió mây chưa mưa", "Tích lũy từng bước nhỏ, chớ vội vàng mưu cầu đại sự."),
    ("Càn", "Đoài"): ("Thiên Trạch Lý", "Dẫm đuôi cọp, cẩn trọng điềm tĩnh", "Đối diện thế khó bằng thái độ lễ độ, hòa nhã."),
    ("Khôn", "Càn"): ("Địa Thiên Thái", "Trời đất giao hòa, thái bình thịnh vượng", "Vận khí hanh thông, nắm bắt cơ hội để kiến tạo."),
    ("Càn", "Khôn"): ("Thiên Địa Bĩ", "Âm dương bế tắc, thời thế đảo điên", "Ẩn nhẫn giữ mình, không thỏa hiệp với cái xấu."),
    ("Càn", "Ly"): ("Thiên Hỏa Đồng Nhân", "Đồng lòng hiệp lực, kết giao bạn lành", "Làm việc nhóm, mở rộng kết nối với cộng đồng."),
    ("Ly", "Càn"): ("Hỏa Thiên Đại Hữu", "Ánh dương rực rỡ, của cải dồi dào", "Chia sẻ tài nguyên, khiêm tốn khi đang ở đỉnh cao."),
    ("Khôn", "Cấn"): ("Địa Sơn Khiêm", "Núi giấu trong đất, khiêm tốn sinh phúc", "Càng giỏi càng khiêm nhường thì vạn sự êm đẹp."),
    ("Chấn", "Khôn"): ("Lôi Địa Dự", "Niềm vui dâng trào, chuẩn bị kỹ lưỡng", "Tận hưởng niềm vui nhưng luôn phòng ngừa rủi ro."),
    ("Đoài", "Chấn"): ("Trạch Lôi Tùy", "Thuận theo thời thế, tùy cơ ứng biến", "Lắng nghe dòng chảy tự nhiên, chớ cưỡng cầu."),
    ("Cấn", "Tốn"): ("Sơn Phong Cổ", "Chỉnh đốn sửa sai, làm mới việc cũ", "Thời điểm tuyệt vời để tái cấu trúc và sửa lỗi quá khứ."),
    ("Khôn", "Đoài"): ("Địa Trạch Lâm", "Thế lớn đang tới, mùa xuân đâm chồi", "Năng lượng dồi dào, hành động ngay kẻo lỡ thời điểm."),
    ("Tốn", "Khôn"): ("Phong Địa Quan", "Quan sát toàn cảnh, thấu hiểu chiều sâu", "Lùi lại một bước nhìn bức tranh lớn trước khi quyết định."),
    ("Ly", "Chấn"): ("Hỏa Lôi Phệ Hạp", "Cắn đứt trở ngại, thực thi pháp luật", "Xử lý dứt điểm điểm nghẽn, không chần chừ do dự."),
    ("Cấn", "Ly"): ("Sơn Hỏa Bí", "Trang hoàng thanh nhã, giản dị chân phương", "Làm đẹp vẻ ngoài nhưng cốt lõi vẫn phải thực chất."),
    ("Cấn", "Khôn"): ("Sơn Địa Bác", "Mòn mỏi sụt lở, thời vận suy vi", "Giữ sức, không manh động, chờ đợi chu kỳ mới."),
    ("Khôn", "Chấn"): ("Địa Lôi Phục", "Dương khí trở lại, khởi đầu chu kỳ mới", "Tia sáng hy vọng xuất hiện, bắt đầu gieo hạt giống mới."),
    ("Càn", "Chấn"): ("Thiên Lôi Vô Vọng", "Chân thật tự nhiên, không vọng tưởng", "Làm đúng phận sự, chớ toan tính mưu mẹo."),
    ("Cấn", "Càn"): ("Sơn Thiên Đại Súc", "Đức hạnh tích chứa, chuẩn bị nghiệp lớn", "Học tập nâng cao năng lực, tích lũy kiến thức sâu sắc."),
    ("Cấn", "Chấn"): ("Sơn Lôi Di", "Nuôi dưỡng thân tâm, chọn lời cẩn thận", "Chú ý lời ăn tiếng nói và việc chăm sóc sức khỏe."),
    ("Đoài", "Tốn"): ("Trạch Phong Đại Quá", "Cột nhà oằn cong, gánh nặng quá sức", "Giảm tải ngay lập tức, cắt bỏ những thứ thừa thãi."),
    ("Khảm", "Khảm"): ("Thuần Khảm", "Hiểm nguy trùng điệp, giữ vững lòng tin", "Dũng cảm đối mặt nghịch cảnh, giữ tâm thanh tịnh."),
    ("Ly", "Ly"): ("Thuần Ly", "Lửa sáng bám củi, trí tuệ soi đường", "Tìm điểm tựa vững chắc, bồi đắp kiến thức chuyên môn."),
    ("Đoài", "Cấn"): ("Trạch Sơn Hàm", "Cảm ứng chân thành, tình duyên gắn kết", "Lắng nghe trực giác và rung cảm chân thật của trái tim."),
    ("Chấn", "Tốn"): ("Lôi Phong Hằng", "Bền vững dài lâu, kiên định mục tiêu", "Kiên trì với con đường đã chọn, chớ đứng núi này trông núi nọ."),
    ("Càn", "Cấn"): ("Thiên Sơn Độn", "Rút lui chiến lược, bảo toàn lực lượng", "Biết lùi đúng lúc là kẻ thông minh, không cố chấp."),
    ("Chấn", "Càn"): ("Lôi Thiên Đại Tráng", "Sức mạnh tráng kiện, cẩn thận húc dậu", "Có thế mạnh nhưng chớ hung hăng, cần mềm mỏng."),
    ("Ly", "Khôn"): ("Hỏa Địa Tấn", "Mặt trời lên cao, thăng tiến rộng mở", "Tỏa sáng năng lực, khẳng định giá trị bản thân."),
    ("Khôn", "Ly"): ("Địa Hỏa Minh Di", "Ánh sáng vùi trong đất, giấu mình chờ thời", "Ẩn mình kín đáo khi xung quanh còn nhiều đố kỵ."),
    ("Tốn", "Ly"): ("Phong Hỏa Gia Nhân", "Gia đạo yên vui, trong ấm ngoài êm", "Tập trung vun vén nội bộ, gốc rễ gia đình, đội nhóm."),
    ("Ly", "Đoài"): ("Hỏa Trạch Khuê", "Bất đồng chia rẽ, hướng đến cái chung", "Chấp nhận sự khác biệt, tìm kiếm điểm tương đồng nhỏ."),
    ("Khảm", "Cấn"): ("Thủy Sơn Kiển", "Núi cao vực sâu, dừng lại xem xét", "Đường cùng chớ bước, quay đầu xem lại phương pháp."),
    ("Chấn", "Khảm"): ("Lôi Thủy Giải", "Sấm tan mưa rào, nút thắt cởi mở", "Mọi vướng mắc bắt đầu được giải tỏa, hành động dứt khoát."),
    ("Cấn", "Đoài"): ("Sơn Trạch Tổn", "Bớt giận kiềm dục, hy sinh trước mắt", "Bớt lợi ích vị kỷ cá nhân để đổi lấy thành công lâu dài."),
    ("Tốn", "Chấn"): ("Phong Lôi Ích", "Gió sấm trợ lực, thêm tài tăng tiến", "Thấy điều tốt thì làm theo, thấy lỗi thì sửa ngay."),
    ("Đoài", "Càn"): ("Trạch Thiên Quải", "Quyết đoán dứt khoát, vạch trần cái xấu", "Dứt khoát với thói quen xấu, không mập mờ."),
    ("Càn", "Tốn"): ("Thiên Phong Cấu", "Tình cờ gặp gỡ, cẩn trọng cám dỗ", "Đề phòng những mối quan hệ bất ngờ thiếu minh bạch."),
    ("Đoài", "Khôn"): ("Trạch Địa Tụy", "Tụ hội đông đảo, đoàn kết phát triển", "Hội tụ tài năng, chung tay vì mục tiêu lớn."),
    ("Khôn", "Tốn"): ("Địa Phong Thăng", "Cây mọc vươn cao, tiến bước từ từ", "Từng bước thăng tiến đều đặn, dựa vào người có tâm."),
    ("Đoài", "Khảm"): ("Trạch Thủy Khốn", "Nước cạn đầm khô, rèn luyện chí khí", "Thời điểm thử thách bản lĩnh, lời nói ít người nghe nên hãy im lặng hành động."),
    ("Khảm", "Tốn"): ("Thủy Phong Tỉnh", "Giếng nước nuôi dân, nguồn lực vô tận", "Bồi đắp nội lực bản thân, nguồn nước trong lành không bao giờ cạn."),
    ("Đoài", "Ly"): ("Trạch Hỏa Cách", "Cải cách đổi mới, bỏ cũ lấy mới", "Thay đổi tư duy và công cụ cũ, cách tân mang lại vận hội mới."),
    ("Ly", "Tốn"): ("Hỏa Phong Đỉnh", "Đúc đỉnh luyện đan, ổn định ngôi vị", "Vận thế vững vàng, tài đức tương xứng vị trí."),
    ("Chấn", "Chấn"): ("Thuần Chấn", "Sấm vang trăm dặm, giật mình tỉnh ngộ", "Tiếng sấm cảnh tỉnh, sửa mình cẩn trọng thì sau bình an."),
    ("Cấn", "Cấn"): ("Thuần Cấn", "Núi đứng im lìm, định tâm bất động", "Dừng lại mọi suy nghĩ lan man, tĩnh tâm thiền định."),
    ("Tốn", "Cấn"): ("Phong Sơn Tiệm", "Tiến bước tuần tự, chim nhạn bay về", "Phát triển từ từ, việc gì vội vàng đều dễ hỏng."),
    ("Chấn", "Đoài"): ("Lôi Trạch Quy Muội", "Lệch lạc chuẩn mực, chớ nên tiến hành", "Chưa đúng thời điểm kết duyên hay ký kết thỏa thuận."),
    ("Chấn", "Ly"): ("Lôi Hỏa Phong", "Thịnh vượng sung túc, mặt trời chính ngọ", "Đang ở thời cực thịnh, chuẩn bị trước cho chu kỳ đi xuống."),
    ("Ly", "Cấn"): ("Hỏa Sơn Lữ", "Khách lạ lữ thứ, cẩn trọng khiêm nhường", "Đang ở môi trường mới hoặc đi xa, hòa nhã để tránh rắc rối."),
    ("Tốn", "Tốn"): ("Thuần Tốn", "Gió thổi luồn sâu, mềm mại thích ứng", "Khéo léo thích nghi như gió thoảng, uốn nắn theo thời cuộc."),
    ("Đoài", "Đoài"): ("Thuần Đoài", "Đầm nước tràn trề, cùng nhau học hỏi", "Niềm vui sẻ chia, gặp gỡ bạn hiền đàm đạo."),
    ("Tốn", "Khảm"): ("Phong Thủy Hoán", "Gió thổi tan mây, giải tỏa ngăn cách", "Xóa bỏ hiểu lầm, hòa tan định kiến cũ."),
    ("Khảm", "Đoài"): ("Thủy Trạch Tiết", "Chừng mực tiết chế, giữ gìn khuôn phép", "Chi tiêu và sinh hoạt có chừng mực, chớ quá trớn."),
    ("Tốn", "Đoài"): ("Phong Trạch Trung Phu", "Chân thành tin cậy, trứng nở thành con", "Lấy chữ Tín làm đầu, chân thành cảm hóa người khác."),
    ("Chấn", "Cấn"): ("Lôi Sơn Tiểu Quá", "Vượt mức chút ít, cẩn trọng chi tiết", "Nên giữ việc nhỏ, tránh mưu tính việc quá tầm tay."),
    ("Khảm", "Ly"): ("Thủy Hỏa Ký Tế", "Việc đã hoàn thành, cẩn thận giữ gìn", "Mục tiêu đã đạt, giữ gìn thành quả quan trọng hơn bành trướng."),
    ("Ly", "Khảm"): ("Hỏa Thủy Vị Tế", "Chưa xong việc, cáo nhỏ qua sông", "Chu kỳ cũ kết thúc, chu kỳ mới mở ra, tiếp tục kiên trì."),
}

LENORMAND_36: List[Dict[str, str]] = [
    {"num": "1", "name": "Kỵ Sĩ (Rider)", "icon": "🏇", "meaning": "Tin tức nhanh chóng, khách ghé thăm, sự khởi đầu mới mẻ."},
    {"num": "2", "name": "Cỏ 4 Lá (Clover)", "icon": "🍀", "meaning": "May mắn bất ngờ, cơ hội nhỏ nhưng chớp nhoáng, niềm vui tức thì."},
    {"num": "3", "name": "Con Tàu (Ship)", "icon": "⛵", "meaning": "Hành trình, du lịch, khoảng cách địa lý hoặc công việc giao thương."},
    {"num": "4", "name": "Ngôi Nhà (House)", "icon": "🏡", "meaning": "Tổ ấm, sự an toàn, gia đình, nền móng vững chắc."},
    {"num": "5", "name": "Cái Cây (Tree)", "icon": "🌳", "meaning": "Sức khỏe, sự trưởng thành lâu dài, nguồn cội, năng lượng bền bỉ."},
    {"num": "6", "name": "Mây Mù (Clouds)", "icon": "☁️", "meaning": "Sự mơ hồ, hiểu lầm tạm thời, bối rối chưa có lời giải."},
    {"num": "7", "name": "Con Rắn (Snake)", "icon": "🐍", "meaning": "Sự phức tạp, phản trắc ngầm, đường vòng, cần hết sức thận trọng."},
    {"num": "8", "name": "Quan Tài (Coffin)", "icon": "⚰️", "meaning": "Sự chấm dứt một giai đoạn, buông bỏ để tái sinh, thay đổi lớn."},
    {"num": "9", "name": "Bó Hoa (Bouquet)", "icon": "💐", "meaning": "Món quà bất ngờ, lời khen ngợi, sự trân trọng và hạnh phúc."},
    {"num": "10", "name": "Lưỡi Hái (Scythe)", "icon": "🌾", "meaning": "Quyết định cắt đứt nhanh chóng, đột ngột, nguy cơ va chạm nhẹ."},
    {"num": "11", "name": "Roi Da & Chổi (Whip)", "icon": "⚔️", "meaning": "Tranh cãi, lặp đi lặp lại, xung đột hoặc rèn luyện thể chất căng thẳng."},
    {"num": "12", "name": "Đôi Chim (Birds)", "icon": "🦉", "meaning": "Trò chuyện, tin nhắn qua lại, sự lo âu lặt vặt ngắn hạn."},
    {"num": "13", "name": "Đứa Trẻ (Child)", "icon": "👶", "meaning": "Sự ngây thơ, dự án mới tinh, bắt đầu từ con số không."},
    {"num": "14", "name": "Con Cáo (Fox)", "icon": "🦊", "meaning": "Công việc hàng ngày, mưu trí mưu sinh, đề phòng bẫy ngầm."},
    {"num": "15", "name": "Con Gấu (Bear)", "icon": "🐻", "meaning": "Tài chính, sếp/người bảo trợ, quyền lực, sự che chở vững vàng."},
    {"num": "16", "name": "Ngôi Sao (Stars)", "icon": "⭐", "meaning": "Hy vọng, dẫn lối, giấc mơ sáng tỏ, cảm hứng dồi dào."},
    {"num": "17", "name": "Chim Cò (Stork)", "icon": "🪶", "meaning": "Sự chuyển dịch, đổi mới không gian sống hoặc thăng tiến tích cực."},
    {"num": "18", "name": "Chú Chó (Dog)", "icon": "🐶", "meaning": "Bạn bè trung thành, sự ủng hộ đáng tin cậy, tri kỷ."},
    {"num": "19", "name": "Tòa Tháp (Tower)", "icon": "🏰", "meaning": "Cơ quan nhà nước, trường học, sự độc lập hoặc cô đơn tạm thời."},
    {"num": "20", "name": "Khu Vườn (Garden)", "icon": "⛲", "meaning": "Cộng đồng, sự kiện công cộng, mạng xã hội, giao lưu đông vui."},
    {"num": "21", "name": "Ngọn Núi (Mountain)", "icon": "⛰️", "meaning": "Vật cản lớn, sự trì hoãn, thách thức cần kiên trì vượt qua."},
    {"num": "22", "name": "Ngã Ba Đường (Crossroads)", "icon": "🛤️", "meaning": "Ngã rẽ cuộc đời, nhiều lựa chọn, cần đưa ra quyết định."},
    {"num": "23", "name": "Đàn Chuột (Mice)", "icon": "🐭", "meaning": "Tổn thất nhỏ giọt, căng thẳng gặm nhấm, hao mòn năng lượng."},
    {"num": "24", "name": "Trái Tim (Heart)", "icon": "❤️", "meaning": "Tình cảm chân thành, niềm đam mê, hòa hợp yêu thương."},
    {"num": "25", "name": "Chiếc Nhẫn (Ring)", "icon": "💍", "meaning": "Cam kết, hợp đồng, hôn ước, sự gắn bó tuần hoàn."},
    {"num": "26", "name": "Cuốn Sách (Book)", "icon": "📖", "meaning": "Bí mật chưa mở, nghiên cứu học tập, kiến thức chuyên sâu."},
    {"num": "27", "name": "Lá Thư (Letter)", "icon": "✉️", "meaning": "Văn bản, email, tài liệu giấy tờ chính thức đến tay."},
    {"num": "28", "name": "Người Nam (Man)", "icon": "👨", "meaning": "Nhân vật nam quan trọng hoặc năng lượng hành động nam tính."},
    {"num": "29", "name": "Người Nữ (Woman)", "icon": "👩", "meaning": "Nhân vật nữ quan trọng hoặc năng lượng trực giác nữ tính."},
    {"num": "30", "name": "Hoa Loa Kèn (Lily)", "icon": "⚜️", "meaning": "Sự thuần khiết, bình an tuổi già, kinh nghiệm từng trải, đạo đức."},
    {"num": "31", "name": "Mặt Trời (Sun)", "icon": "☀️", "meaning": "Chiến thắng vang dội, năng lượng tràn đầy, sự thành công rực rỡ."},
    {"num": "32", "name": "Mặt Trăng (Moon)", "icon": "🌙", "meaning": "Danh tiếng, cảm xúc sâu kín, trực giác tâm linh, nghệ thuật."},
    {"num": "33", "name": "Chiếc Chìa Khóa (Key)", "icon": "🔑", "meaning": "Chìa khóa mở nút thắt, giải pháp quan trọng, tính tất yếu."},
    {"num": "34", "name": "Đàn Cá (Fish)", "icon": "🐟", "meaning": "Dòng tiền trôi chảy, kinh doanh buôn bán, sự dồi dào sung túc."},
    {"num": "35", "name": "Mỏ Neo (Anchor)", "icon": "닻", "meaning": "Sự ổn định lâu dài, bến đỗ bình an, kiên định không dời."},
    {"num": "36", "name": "Cây Thánh Giá (Cross)", "icon": "✝️", "meaning": "Thử thách nhân quả, gánh nặng tâm lý cần vượt qua, bài học định mệnh."},
]


def cast_iching(question: str = "") -> Dict[str, Any]:
    """Gieo quẻ Kinh Dịch bằng phương pháp 3 đồng xu ngẫu nhiên."""
    # Mỗi hào từ dưới (hào 1) lên trên (hào 6).
    # 3 đồng xu: ngửa=3, sấp=2. Tổng: 6 (thái âm động), 7 (thiếu dương), 8 (thiếu âm), 9 (thái dương động)
    raw_lines = []
    lines_binary = []       # 1=dương, 0=âm
    changing_lines = []     # Vị trí các hào động (1-indexed)
    transformed_binary = [] # Quẻ biến

    for i in range(6):
        coins = [random.choice([2, 3]) for _ in range(3)]
        total = sum(coins)
        raw_lines.append(total)
        is_yang = 1 if total in (7, 9) else 0
        lines_binary.append(is_yang)
        if total in (6, 9):
            changing_lines.append(i + 1)
            transformed_binary.append(0 if is_yang == 1 else 1)
        else:
            transformed_binary.append(is_yang)

    lower_trigram_bits = tuple(lines_binary[:3])
    upper_trigram_bits = tuple(lines_binary[3:])
    lower_tri_name, lower_sym, lower_nature, _ = TRIGRAMS.get(lower_trigram_bits, ("Càn", "☰", "", ""))
    upper_tri_name, upper_sym, upper_nature, _ = TRIGRAMS.get(upper_trigram_bits, ("Càn", "☰", "", ""))

    hex_info = HEXAGRAMS_64.get((upper_tri_name, lower_tri_name), ("Quẻ Hỗn Hợp", "Vận thế biến hóa", "Hành động theo chính đạo."))
    hex_name, hex_meaning, hex_advice = hex_info

    # Quẻ Biến nếu có hào động
    transformed_card = None
    if changing_lines:
        t_lower_bits = tuple(transformed_binary[:3])
        t_upper_bits = tuple(transformed_binary[3:])
        t_lower_name, _, _, _ = TRIGRAMS.get(t_lower_bits, ("Khôn", "☷", "", ""))
        t_upper_name, _, _, _ = TRIGRAMS.get(t_upper_bits, ("Khôn", "☷", "", ""))
        t_hex_name, t_hex_meaning, t_hex_advice = HEXAGRAMS_64.get((t_upper_name, t_lower_name), ("Quẻ Biến", "", ""))
        transformed_card = {
            "name": t_hex_name,
            "upper": t_upper_name,
            "lower": t_lower_name,
            "meaning": t_hex_meaning,
            "lines": transformed_binary,
        }

    return {
        "visual_type": "iching",
        "question": question or "Hỏi vận thế tổng quan",
        "hexagram_name": hex_name,
        "upper_trigram": f"{upper_tri_name} ({upper_nature} {upper_sym})",
        "lower_trigram": f"{lower_tri_name} ({lower_nature} {lower_sym})",
        "lines": lines_binary,
        "changing_lines": changing_lines,
        "meaning": hex_meaning,
        "advice": hex_advice,
        "transformed": transformed_card,
    }


def draw_lenormand(question: str = "", count: int = 3) -> Dict[str, Any]:
    """Rút 3 lá bài Lenormand truyền thống."""
    count = max(1, min(5, count))
    chosen = random.sample(LENORMAND_36, count)
    slots = ["Quá khứ / Nguyên nhân", "Hiện tại / Tiêu điểm", "Tương lai / Lời khuyên"] if count == 3 else [f"Lá {i+1}" for i in range(count)]
    
    cards = []
    for i, c in enumerate(chosen):
        cards.append({
            "slot": slots[i] if i < len(slots) else f"Vị trí {i+1}",
            "number": c["num"],
            "name": c["name"],
            "icon": c["icon"],
            "meaning": c["meaning"],
        })

    summary = f"Bộ 3 lá bài mở ra thông điệp: Bắt đầu từ [{chosen[0]['name']}], tâm điểm hiện tại là [{chosen[1]['name']}], hướng tới tương lai với [{chosen[2]['name']}]." if count == 3 else "Kết quả rút bài Lenormand."

    return {
        "visual_type": "lenormand",
        "question": question or "Hỏi xu hướng sự việc",
        "cards": cards,
        "summary": summary,
    }
