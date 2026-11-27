# Akbar VS HanXin

Akbar VS HanXin ghép bốn hàng ô cờ vua với năm hàng giao điểm cờ tướng. Chơi hai người trên cùng máy hoặc đấu với bot Python và chọn bên mình cầm.

## Mở trò chơi

Trên Windows, mở `play.cmd`. Nếu dùng terminal, chạy lệnh sau trong thư mục dự án:

```console
python -m co_xam
```

Cần Python 3.10 trở lên có Tkinter. Trò chơi dùng thư viện chuẩn của Python.

Chọn quân rồi bấm vào một điểm đến được đánh dấu. Nút **Hoàn tác** lùi một nước trong chế độ hai người. Khi đấu máy, nút này đưa ván cờ về trước nước gần nhất của bạn. Đổi chế độ hoặc bên cầm quân giữ nguyên thế cờ hiện tại. Nút **Ván mới** đặt lại bàn cờ.

## Quy ước cho luật kết hợp

- Cờ tướng mở màn. Giới hạn ngòi Pháo tính theo ba lượt đầu của bên cờ tướng.
- Một nước vượt sông dừng ở bờ đến. Nước nhảy đối chiếu cột đích rồi đặt quân ở bờ. Đường kẻ ngoài cùng chỉ có một ô cờ vua kề nó. Các điều kiện chặn đường của từng quân vẫn áp dụng khi qua sông.
- Giới hạn hai bước của Hậu và Tượng cờ vua, cùng quy tắc chặn chân Mã, xét theo phần bàn nơi quân xuất phát. Tốt cờ vua qua sông bằng cách tiến thẳng đến một trong hai giao điểm trống kề cột của nó. Tốt cờ vua ở phần cờ tướng được đi hoặc ăn ngang. Tốt cờ vua tới hàng cuối chọn phong Hậu, Xe, Tượng hoặc Mã.
- Nhập thành giữ luật cờ vua. Nếu Vua đi một nước hợp lệ và làm lộ mặt Tướng, cờ tướng thắng ngay. Các nước đi khác khiến hai quân lộ mặt bị cấm.
- Chiếu hết thắng ván. Hai bên hòa nếu bên đến lượt hết nước hợp lệ khi không bị chiếu, cùng thế cờ lặp lại ba lần, hoặc hai bên đi liên tiếp tổng cộng 100 nước không bắt quân và không đi Tốt.

## Bot Python

Bot dùng mảng bàn cờ một chiều, các tuyến di chuyển tính sẵn và hoàn tác gia tăng. Negamax dùng Alpha–Beta, Iterative Deepening và Quiescence Search. Bảng chuyển vị dùng khóa Zobrist. Bot ưu tiên nước trong bảng, nước ăn theo MVV–LVA, phong cấp và chiếu. Hàm lượng giá pha trộn điểm vật chất và ba bộ bảng điểm vị trí cho khai cuộc, trung cuộc và tàn cuộc.

Có thể chọn ngân sách 1, 3 hoặc 8 giây cho mỗi nước. Khi hết giờ, bot dùng kết quả từ độ sâu đã tìm xong gần nhất.

```console
python -m unittest -v
```
