# CodeQL: "Found multiple dataset directories" Uyarısı

Bu uyarı **projenin veri setlerinden (Kaggle vb.) kaynaklanmaz.** Cursor/VS Code içindeki **CodeQL** eklentisi, kod analizi için kendi veritabanlarını (database/dataset) oluşturur; uyarı bu veritabanlarından birinde birden fazla "dataset" klasörü bulunduğunda çıkar.

## Ne anlama geliyor?

- CodeQL, projeyi analiz ederken `codeql_db` altında dil bazlı klasörler oluşturur (örn. `db-python`).
- Bazen eski analizler veya farklı diller için oluşturulmuş birden fazla dataset klasörü kalır.
- Eklenti bunlardan birini seçip kullanıyor ve hangisini kullandığını bu uyarı ile söylüyor.

## Ne yapabilirsiniz?

### 1. Otomatik: Script ile temizleme (önerilen)

Projede bu script var; Cursor **kapalıyken** çalıştırın:

```powershell
# Proje kökünden (TriAIge klasöründen)
.\scripts\clean-codeql-databases.ps1
```

Script, Cursor workspace storage içindeki tüm `codeql_db` klasörlerini bulur, size listeler ve onaylarsanız siler. Sonrasında Cursor'u açtığınızda CodeQL tek bir temiz veritabanı oluşturur; "multiple dataset directories" uyarısı kaybolur.

- Onay sormadan silmek için: `.\scripts\clean-codeql-databases.ps1 -Force`
- İlk kez çalıştırmada "execution policy" hatası alırsanız:  
  `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

### 2. Manuel: Command Palette ile veritabanı seçme/silme

1. **Command Palette** açın: `Ctrl+Shift+P` (Windows) / `Cmd+Shift+P` (Mac)
2. **"CodeQL: Delete Database"** veya **"CodeQL: Select Database"** yazın
3. Eski / kullanılmayan veritabanını silin veya kullanmak istediğiniz tek bir tane seçin
4. Gerekirse **"CodeQL: Create Database"** ile sadece kullandığınız dil (örn. Python) için yeni bir veritabanı oluşturun

### 3. Manuel: Workspace storage yolunu kendiniz silmek

Uyarıda gördüğünüz yol Cursor'ın workspace storage'ındadır:
`...\workspaceStorage\...\GitHub.vscode-codeql\...\codeql_db\`

- Cursor'ı kapatın
- Bu `codeql_db` klasörünü Explorer'dan elle silebilirsiniz
- Cursor'ı tekrar açıp CodeQL'in veritabanını yeniden oluşturmasını bekleyin

## Özet

- **Proje verisi:** TriAIge'daki Kaggle/JSON veri kaynakları bu uyarıdan etkilenmez.
- **CodeQL:** Sadece eklentinin kendi analiz veritabanlarıyla ilgili. Eski/çoklu dataset'leri silip tek bir veritabanı kullanmak uyarıyı giderir.
