# Mẫu câu hỏi cần bạn duyệt — GSM8K development

Đã chọn 24 câu chỉ từ train bằng hash/seed, trước khi xem kết quả model. Một câu bị loại vì mơ hồ; pilot dùng 23 câu (11 train, 12 calibration). Cả hai phần đều chỉ dùng để phát triển, không phải test.

Bạn đọc năm câu đầu và những câu có ghi chú cách hiểu (10, 15, 22, 24) trước. Đánh dấu câu nào diễn đạt mơ hồ hoặc lời giải chưa thuyết phục. Trước khi đưa vào bài báo, cần duyệt toàn bộ mẫu và ghi người duyệt/ngày; hiện chưa có xác nhận của con người.

Người duyệt: chưa ghi. Ngày duyệt: chưa ghi. Phản hồi/câu cần sửa: chưa ghi.

## 1. gsm8k-dev-05545 — train

An agricultural cooperative must ship 6500 kg of potatoes. During transport by truck, 150 kg are damaged and therefore cannot be sold. The potatoes are distributed in 50 kg bags, each bag being sold for $72. What will the sale of the potatoes bring?

Đáp án nguồn: **9144**. Phép tính kiểm tra: `(6500-150)/50*72`.

Trừ phần hỏng, chia thành túi 50 kg, rồi nhân giá mỗi túi.

## 2. gsm8k-dev-02161 — calibration

John's shirt cost 60% more than his pants.  His pants cost $50.  How much was John's outfit?

Đáp án nguồn: **130**. Phép tính kiểm tra: `50*(1+60/100)+50`.

Áo bằng 160% giá quần; cộng cả áo và quần.

## 3. gsm8k-dev-05507 — train

The first tank is 300 liters filled while the second tank is 450 liters filled. The second tank is only 45% filled. If the two tanks have the same capacity, how many more liters of water are needed to fill the two tanks?

Đáp án nguồn: **1250**. Phép tính kiểm tra: `2*(450/(45/100))-300-450`.

Suy ra dung tích mỗi bể từ bể thứ hai, rồi trừ lượng nước hiện có.

## 4. gsm8k-dev-00330 — calibration

Samuel bought 2 dozen doughnuts and Cathy bought 3 dozen doughnuts. They planned to share the doughnuts evenly with their 8 other friends. How many doughnuts will each of them receive?

Đáp án nguồn: **6**. Phép tính kiểm tra: `((2+3)*12)/(2+8)`.

Có 60 bánh và 10 người, tính cả Samuel và Cathy.

## 5. gsm8k-dev-05994 — train

John wants to lose weight.  He eats 1800 calories a day and burns 2300 a day.  If he needs to burn 4000 calories to lose 1 pound how many days will it take to lose 10 pounds?

Đáp án nguồn: **80**. Phép tính kiểm tra: `10*4000/(2300-1800)`.

Theo giả định của bài toán: cần hụt 40.000 calorie, mỗi ngày hụt 500.

## 6. gsm8k-dev-01342 — calibration

Sasha can complete 15 questions an hour. If she has 60 questions to complete and she works for 2 hours, how many questions does she still need to complete?

Đáp án nguồn: **30**. Phép tính kiểm tra: `60-15*2`.

Trừ 30 câu đã làm trong 2 giờ khỏi tổng 60 câu.

## 7. gsm8k-dev-05093 — train

Kevin is taking a 600-mile trip, traveling at a rate of 50 miles per hour. How much faster must he travel to decrease his travel time by 4 hours?

Đáp án nguồn: **25**. Phép tính kiểm tra: `600/(600/50-4)-50`.

Thời gian cũ 12 giờ, mới 8 giờ; vận tốc mới 75 mph, tăng 25.

## 8. gsm8k-dev-00482 — calibration

Julia is performing in her high school musical this weekend and her family wants to come to the show. Tickets are $12 for adults and $10 for children. If her mom, dad, grandma, and three little sisters come to the show, how much will the total be for their tickets?

Đáp án nguồn: **66**. Phép tính kiểm tra: `3*12+3*10`.

Ba người lớn và ba trẻ em.

## 9. gsm8k-dev-00077 — train

A garden produced 237 potatoes, 60 fewer cucumbers and twice as many peppers than the cucumbers. How many vegetables did the garden produce?

Đáp án nguồn: **768**. Phép tính kiểm tra: `237+(237-60)+2*(237-60)`.

Dưa chuột là 177; ớt là 354; cộng ba loại.

## 10. gsm8k-dev-05565 — calibration

Tree Elementary School is raising money for a new playground. Mrs. Johnson’s class raised $2300, which is twice the amount that Mrs. Sutton’s class raised. Mrs. Sutton’s class raised 8 times less than Miss Rollin’s class. Miss Rollin’s class raised a third of the total amount raised by the school. How much money did the school raise for the playground if 2% will be deducted for administration fees?

Đáp án nguồn: **27048**. Phép tính kiểm tra: `(2300/2)*8*3*(98/100)`.

Hiểu “8 times less” là bằng 1/8; tính tổng trường và số còn lại sau phí 2%.

## 11. gsm8k-dev-05794 — train

The dog toys Samantha buys for her dog are "buy one get one half off" and all cost $12.00 each. She buys 4 toys.  How much does she spend on dog toys?

Đáp án nguồn: **36**. Phép tính kiểm tra: `(12+12/2)*2`.

Bốn đồ chơi tạo hai cặp: mỗi cặp giá 12+6.

## 12. gsm8k-dev-04607 — calibration

Nate is reading a 400-page book. He finished reading 20% of the book. How many pages does he need to read to finish the book?

Đáp án nguồn: **320**. Phép tính kiểm tra: `400*(1-20/100)`.

Còn 80% của 400 trang.

## 13. gsm8k-dev-01851 — train

Drew is reseeding his lawn with grass seed. One bag of grass seed covers 250 square feet of lawn. His lawn is 22 feet from the house to the curb and 36 feet from side to side. He bought four bags of seed. How many extra square feet could the leftover grass seed cover after Drew reseeds his lawn?

Đáp án nguồn: **208**. Phép tính kiểm tra: `4*250-22*36`.

Diện tích có thể gieo từ bốn túi trừ diện tích sân.

## 14. gsm8k-dev-02814 — calibration

Leila went to the supermarket to get some groceries. Then she headed to her mechanic to get her automobile fixed. If fixing her automobile cost $350 which was $50 more than thrice the amount she spent at the supermarket, how much has she spent altogether?

Đáp án nguồn: **450**. Phép tính kiểm tra: `350+(350-50)/3`.

Chi siêu thị bằng (350-50)/3; cộng phí sửa xe.

## 15. gsm8k-dev-03628 — LOẠI

When Jeffrey walks, for every three steps forward, he takes two steps backwards.  Therefore, if the distance between the house and the mailbox is 66 steps, what is the total number of steps Jeffrey takes when he goes from the house to the mailbox?

Đáp án nguồn: **330**. Phép tính kiểm tra: `66/(3-2)*(3+2)`.

Đáp án nguồn đếm 66 chu kỳ đầy đủ: 330 bước. Nhưng lần đầu chạm đích là 63*5+3=318 bước. Loại trước generation vì mơ hồ.

## 16. gsm8k-dev-01628 — calibration

Grace is filling her pool in the backyard with a hose that sprays 50 gallons/hour. She waited for 3 hours but the pool wasn't full, so she decides to add another hose that sprays 70 gallons/hour, and after 2 more hours the pool is full. How much water can Grace’s pool contain?

Đáp án nguồn: **390**. Phép tính kiểm tra: `3*50+2*(50+70)`.

Ba giờ vòi đầu, sau đó hai giờ cả hai vòi cùng chạy.

## 17. gsm8k-dev-07294 — train

Brenda is a vet who needs to spay some cats and twice as many dogs. If she needs to spay 21 animals total today, how many cats does she need to spay?

Đáp án nguồn: **7**. Phép tính kiểm tra: `21/(1+2)`.

Mỗi nhóm gồm 1 mèo và 2 chó; 21/3 mèo.

## 18. gsm8k-dev-01492 — calibration

Mr Julien's store has 400 marbles remaining after the previous day's sales. Twenty customers came into the store, and each bought 15 marbles. How many marbles remain in the store?

Đáp án nguồn: **100**. Phép tính kiểm tra: `400-20*15`.

Trừ tổng số bi đã bán.

## 19. gsm8k-dev-04765 — train

To increase her water intake to the recommended level by her doctor, Happy has to take 40% more cups of water than she takes now. If she is currently drinking 15 cups of water every week, what's the recommended number of cups per week?

Đáp án nguồn: **21**. Phép tính kiểm tra: `15*(1+40/100)`.

Tăng 40% từ 15 cốc một tuần.

## 20. gsm8k-dev-04625 — calibration

Farmer Randy has 1700 acres of cotton he needs to have planted in 5 days.  With a crew of 2 tractors working for 2 days and then a crew of 7 tractors working for another 3 days, how many acres of cotton per day does each tractor need to plant to meet their planting deadline?

Đáp án nguồn: **68**. Phép tính kiểm tra: `1700/(2*2+7*3)`.

Có 25 ngày-máy kéo; chia diện tích cho tổng đó.

## 21. gsm8k-dev-00196 — train

Mary bought 5 boxes of drinks at $6 each box and 10 boxes of pizzas at $14 each box for her pizza party. She paid $200 for all the items. How much change did she get back?

Đáp án nguồn: **30**. Phép tính kiểm tra: `200-5*6-10*14`.

Trừ chi phí đồ uống và pizza khỏi 200.

## 22. gsm8k-dev-04046 — calibration

Laura took six trips to park.  On each trip, she spent 2 hours at the park and an additinal 30 minutes walking to and from the park.  What percentage of the total time she took for her trips to the park did Laura spend in the park?

Đáp án nguồn: **80**. Phép tính kiểm tra: `6*2/(6*(2+30/60))*100`.

Hiểu 30 phút là tổng đi-về mỗi chuyến; tỷ lệ thời gian ở công viên là 80%.

## 23. gsm8k-dev-02834 — train

Annie does a survey of the sixth-grade classes to see who prefers pretzels to goldfish. In Miss Johnson's class, 1/6 of the students preferred goldfish. In Mr. Feldstein's class, 2/3rds of the students preferred goldfish. In Ms. Henderson's class, 1/5 of the students prefer goldfish. If each class has 30 students, how many people total prefer goldfish?

Đáp án nguồn: **31**. Phép tính kiểm tra: `30/6+30*2/3+30/5`.

Đếm số người thích goldfish trong mỗi lớp rồi cộng.

## 24. gsm8k-dev-00083 — calibration

Irene earns $500 if she works for 40 hours a week and gets an extra $20 for every hour of overtime. If she worked 50 hours last week, calculate her total income.

Đáp án nguồn: **700**. Phép tính kiểm tra: `500+(50-40)*20`.

Theo đáp án nguồn: 500 cho 40 giờ, mỗi giờ ngoài 40 giờ được 20 thêm.
