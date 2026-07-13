# CineGraph — Sistem Rekomendasi Film Berbasis Teori Graf

Proyek Struktur Data yang memodelkan koleksi film sebagai **graf tak berarah dan
berbobot**: setiap film adalah **vertex (node)**, dan setiap kemiripan genre,
sutradara, atau aktor antar dua film adalah **edge** berbobot.

## 1. Cara Menjalankan

```bash
pip install -r requirements.txt
python app.py
```

Buka `http://127.0.0.1:5000` di browser.

## 2. Struktur Data Graph (`app.py`)

Graph diimplementasikan manual sebagai **Adjacency List** (tanpa library graph
pihak ketiga seperti networkx), pada class `MovieGraph`:

```python
self.nodes = {}                     # id -> data film
self.adjacency = defaultdict(list)  # id -> [{to, relation, weight}, ...]
```

### Pembentukan Edge (`build_edges_from_attributes`)
Untuk setiap pasangan film (kompleksitas O(V²) satu kali saat startup):
- **Genre sama** → bobot = 1 × jumlah genre yang sama
- **Sutradara sama** → bobot = 3 (paling kuat)
- **Aktor sama** → bobot = 2 × jumlah aktor yang sama

### Algoritma 1 — BFS Lintasan Terpendek (`bfs_shortest_path`)
Mencari jalur terpendek (jumlah langkah minimum) antar dua film menggunakan
**Breadth-First Search** klasik, dipakai pada fitur *"Lihat Hubungan Film"*
saat dua node diklik pada peta graf penuh.

### Algoritma 2 — Weighted Graph Traversal (`weighted_recommendation`)
Algoritma rekomendasi inti, bukan sekadar filter atribut:
1. Mulai dari node film yang dipilih (depth 0).
2. Jelajahi tetangga langsung (depth 1) → skor bertambah penuh sesuai bobot edge.
3. Jelajahi tetangga dari tetangga (depth 2) → skor bertambah dengan bobot
   yang di-*decay* (dikalikan 0.5), sehingga hubungan tidak langsung tetap
   dihitung tapi lebih rendah pengaruhnya.
4. Semua film diberi skor akumulatif dan diurutkan menurun.
5. Alasan (`reasons`) dikumpulkan dari setiap edge yang dilalui, sehingga
   sistem bisa menjelaskan **mengapa** sebuah film direkomendasikan.

## 3. API Endpoints

| Endpoint | Keterangan |
|---|---|
| `GET /api/movies` | Daftar seluruh film (untuk dropdown) |
| `GET /api/movie/<id>` | Detail satu film |
| `GET /api/recommend/<id>?depth=2&top_n=6` | Rekomendasi berbasis graf + alasan |
| `GET /api/graph` | Seluruh graf (node & edge) untuk visualisasi |
| `GET /api/graph/ego/<id>?depth=1` | Sub-graf (ego graph) di sekitar satu film |
| `GET /api/path/<id1>/<id2>` | Lintasan terpendek (BFS) antar dua film |

## 4. Fitur Utama (Frontend)

- **Pemilihan node awal** — dropdown untuk memilih film favorit sebagai
  titik awal penelusuran graf.
- **Visualisasi graf interaktif** (`vis-network`) — tombol "Lihat Hubungan
  Film" menampilkan ego-graph film terpilih; tombol "Peta Graf Penuh"
  menampilkan seluruh graf dan mendukung klik dua node untuk mencari lintasan
  terpendek antar keduanya.
- **Penjelasan alasan rekomendasi** — tiap kartu rekomendasi menampilkan
  kalimat alasan otomatis + chip berwarna (Genre/Sutradara/Aktor) sesuai
  edge yang menghubungkan.
- **Notasi vertex (V01, V02, ...)** pada tiap poster, merefleksikan
  penomoran vertex dalam graf.
- **Trailer resmi** dibuka di tab baru (`target="_blank"`) agar tidak
  bergantung pada embed YouTube saat presentasi (menghindari Error 153).
- **Desain responsif** penuh untuk HP dan laptop.

## 5. Menambah Film Baru

Tambahkan entri baru pada list `RAW_MOVIES` di `app.py` dengan struktur yang
sama (id, title, year, duration, director, actors, genre, curator_score,
synopsis, trailer, color). Edge akan terbentuk otomatis saat server
dijalankan ulang — tidak perlu menulis edge manual.
