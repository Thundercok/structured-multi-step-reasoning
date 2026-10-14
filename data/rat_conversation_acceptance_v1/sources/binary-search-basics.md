# Binary search — ví dụ ngắn

Mảng phải tăng dần; chỉ số bắt đầu từ 0. Xét đoạn [l,r], mid=(l+r)//2. Bằng đích thì dừng. Nhỏ hơn đích: l=mid+1; lớn hơn đích: r=mid-1. Loại mid vì đã xét nó. Nếu l>r thì không tìm thấy.

Với [1,4,7,9,12,16,20], tìm16: mid=3, giá trị9, đặt l=4; sau đó mid=5, giá trị16, trả index5. Tìm9 dừng ở mid=3, index3.
