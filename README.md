# Con Nước – ứng dụng Android

Ứng dụng Android dự báo thủy triều thiên văn tại mọi kinh–vĩ độ (mô hình EOT20, hằng số trạm
TICON-4 / NOAA / CHS), đóng gói từ trang web một file `Con_nuoc.html`. Toàn bộ dữ liệu mô hình,
phông chữ và thư viện được đóng kèm nên ứng dụng **chạy hoàn toàn offline**.

## Cài đặt

1. Mở trang [Releases](../../releases/tag/apk-latest) trên điện thoại, tải `ConNuoc.apk`.
2. Mở file vừa tải; nếu Android hỏi, cho phép trình duyệt / trình quản lý file "cài ứng dụng không rõ nguồn gốc".
3. Yêu cầu Android 7.0 trở lên.

Mỗi lần đẩy (push) mã lên GitHub, workflow **Build APK** (`.github/workflows/android.yml`) tự build
lại và thay file trong release `apk-latest`; file APK cũng có trong mục *Artifacts* của lần chạy.

## Cấu trúc

| Đường dẫn | Nội dung |
| --- | --- |
| `app/src/main/java/.../MainActivity.java` | WebView toàn màn hình, phục vụ `assets/www` qua `https://appassets.androidplatform.net` |
| `app/src/main/assets/www/index.html` | Trang Con Nước (đã tách dữ liệu nhúng ra file riêng) |
| `app/src/main/assets/www/emb/` | Dữ liệu mô hình EOT20, đường bờ, trạm triều (gzip) |
| `app/src/main/assets/www/android.js` | Cầu nối với Android: sao chép CSV, màu thanh hệ thống theo giao diện sáng/tối |
| `tools/build_web.py` | Tạo lại `assets/www` từ một file `Con_nuoc.html` mới |

## Cập nhật từ file HTML mới

```bash
rm -rf app/src/main/assets/www/emb app/src/main/assets/www/index.html
python3 tools/build_web.py duong/dan/Con_nuoc.html
```

Sau đó tăng `versionCode` / `versionName` trong `app/build.gradle`, commit và push.

## Build trên máy

Cần JDK 17 và Android SDK (đặt `ANDROID_HOME` hoặc `sdk.dir` trong `local.properties`):

```bash
./gradlew assembleRelease
```

APK nằm ở `app/build/outputs/apk/release/app-release.apk`.

## Ký ứng dụng

Không có cấu hình gì thêm thì APK được ký bằng khóa debug của máy build. Khóa debug trên GitHub
Actions đổi theo từng lần chạy, nên khi cài bản mới có thể phải gỡ bản cũ trước. Để các bản sau
cài đè được, tạo khóa riêng một lần:

```bash
keytool -genkeypair -v -keystore connuoc.jks -alias connuoc -keyalg RSA -keysize 2048 -validity 10000
```

rồi thêm vào *Settings → Secrets and variables → Actions* của repo:
`CONNUOC_KEYSTORE_BASE64` (kết quả `base64 -w0 connuoc.jks`), `CONNUOC_KEYSTORE_PASSWORD`,
`CONNUOC_KEY_ALIAS`, `CONNUOC_KEY_PASSWORD`. Giữ file `connuoc.jks` cẩn thận, không commit vào repo.

## Nguồn dữ liệu

EOT20 (DGFI-TUM, CC BY 4.0); hằng số trạm TICON-4 / NOAA / CHS qua openwatersio/tide-database;
tính toán bằng @neaps/tide-predictor (MIT). Triều thiên văn: không gồm nước dâng do bão, gió mùa
hay lũ; không dùng thay bảng thủy triều chính thức cho dẫn đường hàng hải.
