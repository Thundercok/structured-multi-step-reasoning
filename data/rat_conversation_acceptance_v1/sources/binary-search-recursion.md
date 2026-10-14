# Binary search — cách viết đệ quy

Đệ quy cũng tìm trên mảng đã sắp xếp. Nếu l>r thì không tìm thấy. Nếu a[mid] bằng đích thì trả mid; nếu nhỏ hơn đích, gọi lại trên [mid+1,r]; nếu lớn hơn, gọi lại trên [l,mid-1]. Mỗi lần gọi phải thu nhỏ đoạn tìm kiếm.
