# =========================================================
# PENGEMBANGAN SISTEM REKOMENDASI FILM BERBASIS TEORI GRAF
# =========================================================
# Struktur Data Utama : Graph (Adjacency List, undirected, weighted)
# Algoritma            : Weighted Graph Traversal (BFS berlapis + decay)
#                         untuk rekomendasi, dan BFS murni untuk
#                         mencari lintasan terpendek (shortest path)
#                         antar dua film.
# =========================================================

from flask import Flask, jsonify, render_template, request, abort
from collections import deque, defaultdict
import itertools

app = Flask(__name__)


# ---------------------------------------------------------
# 1. STRUKTUR DATA GRAPH
# ---------------------------------------------------------
class MovieGraph:
    """
    Graph tak berarah (undirected) & berbobot (weighted).
    Direpresentasikan sebagai Adjacency List:
        adjacency = {
            node_id: [ {to, relation, weight}, ... ]
        }
    Node   = Film
    Edge   = Hubungan (Genre / Sutradara / Aktor) beserta bobotnya
    """

    def __init__(self):
        self.nodes = {}                     # id -> data film (dict)
        self.adjacency = defaultdict(list)  # id -> list edge

    # ---------- pembentukan graph ----------
    def add_movie(self, movie: dict):
        self.nodes[movie["id"]] = movie

    def add_edge(self, id1, id2, relation, weight):
        self.adjacency[id1].append({"to": id2, "relation": relation, "weight": weight})
        self.adjacency[id2].append({"to": id1, "relation": relation, "weight": weight})

    def build_edges_from_attributes(self):
        """
        Edge dibangun OTOMATIS dari kemiripan atribut antar film:
          - Genre yang sama       -> bobot 1 per genre yang sama
          - Sutradara yang sama   -> bobot 3 (kuat)
          - Aktor yang sama       -> bobot 2 per aktor yang sama
        Kompleksitas: O(V^2) satu kali saat graph dibangun (V = jumlah film).
        """
        ids = list(self.nodes.keys())
        for a, b in itertools.combinations(ids, 2):
            ma, mb = self.nodes[a], self.nodes[b]

            shared_genre = set(ma["genre"]) & set(mb["genre"])
            if shared_genre:
                self.add_edge(a, b, f"Genre:{'/'.join(sorted(shared_genre))}", weight=1 * len(shared_genre))

            if ma["director"] == mb["director"]:
                self.add_edge(a, b, f"Sutradara:{ma['director']}", weight=3)

            shared_actor = set(ma["actors"]) & set(mb["actors"])
            if shared_actor:
                self.add_edge(a, b, f"Aktor:{'/'.join(sorted(shared_actor))}", weight=2 * len(shared_actor))

    # ---------- utilitas ----------
    def neighbors(self, node_id):
        return self.adjacency.get(node_id, [])

    # ---------- ALGORITMA 1: BFS - Lintasan terpendek ----------
    def bfs_shortest_path(self, start, goal):
        if start not in self.nodes or goal not in self.nodes:
            return None, None
        if start == goal:
            return [start], []

        visited = {start}
        queue = deque([(start, [start], [])])

        while queue:
            current, path, edges = queue.popleft()
            for edge in self.neighbors(current):
                nxt = edge["to"]
                if nxt in visited:
                    continue
                new_path = path + [nxt]
                new_edges = edges + [edge["relation"]]
                if nxt == goal:
                    return new_path, new_edges
                visited.add(nxt)
                queue.append((nxt, new_path, new_edges))
        return None, None  # tidak terhubung

    # ---------- ALGORITMA 2: Weighted traversal untuk rekomendasi ----------
    def weighted_recommendation(self, start, depth=2, decay=0.5, top_n=6):
        """
        Menjelajah graph berlapis (mirip BFS berbobot) mulai dari node 'start'.
        - Tetangga langsung (depth 1)   -> bobot penuh
        - Tetangga dari tetangga (depth 2) -> bobot terdiskon (decay)
        Skor akhir = akumulasi bobot edge dari semua lintasan menuju node tsb.
        """
        if start not in self.nodes:
            return []

        scores = defaultdict(float)
        reasons = defaultdict(set)
        best_depth = {}

        frontier = [(start, 1.0)]
        seen_this_run = {start}

        for level in range(1, depth + 1):
            next_frontier = []
            for node_id, multiplier in frontier:
                for edge in self.neighbors(node_id):
                    nxt = edge["to"]
                    if nxt == start:
                        continue
                    gained = edge["weight"] * multiplier
                    scores[nxt] += gained
                    reasons[nxt].add(edge["relation"])
                    if nxt not in best_depth:
                        best_depth[nxt] = level
                    if nxt not in seen_this_run:
                        seen_this_run.add(nxt)
                        next_frontier.append((nxt, multiplier * decay))
            frontier = next_frontier

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        results = []
        for movie_id, score in ranked:
            results.append({
                "movie": self.nodes[movie_id],
                "score": round(score, 2),
                "reasons": sorted(reasons[movie_id]),
                "depth": best_depth[movie_id],
            })
        return results

    # ---------- Ambil sub-graph (ego graph) untuk visualisasi ----------
    def ego_graph(self, start, depth=1):
        if start not in self.nodes:
            return [], []
        visited = {start}
        nodes_out = [start]
        edges_out = []
        frontier = [start]

        for _ in range(depth):
            next_frontier = []
            for node_id in frontier:
                for edge in self.neighbors(node_id):
                    pair_key = tuple(sorted([node_id, edge["to"]])) + (edge["relation"],)
                    if pair_key not in {tuple(sorted([e["from"], e["to"]])) + (e["relation"],) for e in edges_out}:
                        edges_out.append({
                            "from": node_id, "to": edge["to"],
                            "relation": edge["relation"], "weight": edge["weight"]
                        })
                    if edge["to"] not in visited:
                        visited.add(edge["to"])
                        nodes_out.append(edge["to"])
                        next_frontier.append(edge["to"])
            frontier = next_frontier

        return nodes_out, edges_out

    def to_full_graph_json(self):
        nodes = [{"id": mid, "label": m["title"], "genre": m["genre"]} for mid, m in self.nodes.items()]
        seen = set()
        edges = []
        for node_id, edge_list in self.adjacency.items():
            for e in edge_list:
                key = tuple(sorted([node_id, e["to"]])) + (e["relation"],)
                if key in seen:
                    continue
                seen.add(key)
                edges.append({
                    "from": node_id, "to": e["to"],
                    "relation": e["relation"],
                    "type": e["relation"].split(":")[0],
                    "weight": e["weight"],
                })
        return nodes, edges


# ---------------------------------------------------------
# 2. DATASET FILM (bisa diganti / ditambah bebas)
# ---------------------------------------------------------
RAW_MOVIES = [
    dict(id="dune2", title="Dune: Part Two", year=2024, duration=166,
         director="Denis Villeneuve", actors=["Timothée Chalamet", "Zendaya"],
         genre=["Sci-Fi", "Adventure"], curator_score=9.2,
         synopsis="Paul Atreides bersatu dengan Chani dan Fremen dalam perjalanan balas dendam terhadap konspirator yang menghancurkan keluarganya.",
         trailer="U2Qp5pL3ovA", color="#d97706"),
    dict(id="br2049", title="Blade Runner 2049", year=2017, duration=164,
         director="Denis Villeneuve", actors=["Ryan Gosling", "Harrison Ford"],
         genre=["Sci-Fi", "Drama"], curator_score=8.8,
         synopsis="Seorang blade runner muda menemukan rahasia lama yang dapat menjerumuskan masyarakat yang tersisa ke dalam kekacauan.",
         trailer="gCcx85zbxz4", color="#0891b2"),
    dict(id="arrival", title="Arrival", year=2016, duration=116,
         director="Denis Villeneuve", actors=["Amy Adams", "Jeremy Renner"],
         genre=["Sci-Fi", "Drama"], curator_score=8.6,
         synopsis="Seorang ahli bahasa direkrut militer untuk berkomunikasi dengan makhluk asing setelah pesawat misterius mendarat di seluruh dunia.",
         trailer="tFMo3UJ4B4g", color="#0891b2"),
    dict(id="interstellar", title="Interstellar", year=2014, duration=169,
         director="Christopher Nolan", actors=["Matthew McConaughey", "Anne Hathaway"],
         genre=["Sci-Fi", "Adventure", "Drama"], curator_score=9.0,
         synopsis="Sekelompok penjelajah memanfaatkan lubang cacing untuk melampaui batas perjalanan antariksa manusia demi menyelamatkan umat manusia.",
         trailer="zSWdZVtXT7E", color="#7c3aed"),
    dict(id="inception", title="Inception", year=2010, duration=148,
         director="Christopher Nolan", actors=["Leonardo DiCaprio", "Elliot Page"],
         genre=["Sci-Fi", "Action"], curator_score=8.9,
         synopsis="Seorang pencuri yang mencuri informasi lewat mimpi diberi tugas terakhir: menanam ide, bukan mencurinya.",
         trailer="YoHD9XEInc0", color="#7c3aed"),
    dict(id="oppenheimer", title="Oppenheimer", year=2023, duration=180,
         director="Christopher Nolan", actors=["Cillian Murphy", "Emily Blunt"],
         genre=["Drama", "History", "Biography"], curator_score=9.1,
         synopsis="Kisah J. Robert Oppenheimer dan perannya dalam pengembangan bom atom di tengah dilema moral yang mendalam.",
         trailer="uYPbbksJxIg", color="#7c3aed"),
    dict(id="tenet", title="Tenet", year=2020, duration=150,
         director="Christopher Nolan", actors=["John David Washington", "Robert Pattinson"],
         genre=["Sci-Fi", "Action"], curator_score=7.9,
         synopsis="Seorang agen rahasia mempelajari cara memanipulasi arus waktu untuk mencegah Perang Dunia III.",
         trailer="LdOM0x0XDMo", color="#7c3aed"),
    dict(id="tdk", title="The Dark Knight", year=2008, duration=152,
         director="Christopher Nolan", actors=["Christian Bale", "Heath Ledger"],
         genre=["Action", "Crime", "Drama"], curator_score=9.3,
         synopsis="Batman menghadapi Joker, seorang kriminal jenius yang ingin membuktikan bahwa siapa pun bisa jatuh ke dalam kegelapan.",
         trailer="EXeTwQWrcwY", color="#7c3aed"),
    dict(id="dunkirk", title="Dunkirk", year=2017, duration=106,
         director="Christopher Nolan", actors=["Fionn Whitehead", "Tom Hardy"],
         genre=["War", "Action", "Drama"], curator_score=8.3,
         synopsis="Kisah evakuasi tentara sekutu dari pantai Dunkirk saat dikepung pasukan Jerman dalam Perang Dunia II.",
         trailer="F-eMLFxGsjA", color="#7c3aed"),
    dict(id="wonka", title="Wonka", year=2023, duration=116,
         director="Paul King", actors=["Timothée Chalamet", "Olivia Colman"],
         genre=["Fantasy", "Musical", "Family"], curator_score=8.0,
         synopsis="Perjalanan awal Willy Wonka muda saat pertama kali membangun reputasinya sebagai pembuat cokelat.",
         trailer="otNh9bTjXWg", color="#db2777"),
    dict(id="martian", title="The Martian", year=2015, duration=144,
         director="Ridley Scott", actors=["Matt Damon", "Jessica Chastain"],
         genre=["Sci-Fi", "Adventure"], curator_score=8.5,
         synopsis="Seorang astronot terdampar di Mars dan harus bertahan hidup sambil menunggu misi penyelamatan.",
         trailer="ej3ioOneTy8", color="#d97706"),
    dict(id="gravity", title="Gravity", year=2013, duration=91,
         director="Alfonso Cuarón", actors=["Sandra Bullock", "George Clooney"],
         genre=["Sci-Fi", "Drama"], curator_score=8.1,
         synopsis="Dua astronot berjuang bertahan hidup setelah puing satelit menghancurkan pesawat ulang-alik mereka.",
         trailer="OiTiKOy59o4", color="#0891b2"),
    dict(id="madmax", title="Mad Max: Fury Road", year=2015, duration=120,
         director="George Miller", actors=["Tom Hardy", "Charlize Theron"],
         genre=["Action", "Adventure"], curator_score=8.7,
         synopsis="Di dunia pasca-kiamat, Max bergabung dengan Furiosa untuk melarikan diri dari tiran gurun yang kejam.",
         trailer="hEJnMQG9ev8", color="#dc2626"),
    dict(id="br1982", title="Blade Runner", year=1982, duration=117,
         director="Ridley Scott", actors=["Harrison Ford", "Rutger Hauer"],
         genre=["Sci-Fi", "Drama"], curator_score=8.4,
         synopsis="Seorang blade runner diburu untuk memburu replika buatan yang melarikan diri kembali ke Bumi.",
         trailer="eogpIG53Cis", color="#0891b2"),
    dict(id="poorthings", title="Poor Things", year=2023, duration=141,
         director="Yorgos Lanthimos", actors=["Emma Stone", "Mark Ruffalo"],
         genre=["Fantasy", "Comedy", "Drama"], curator_score=8.2,
         synopsis="Seorang wanita muda dihidupkan kembali oleh ilmuwan eksentrik dan menjelajahi dunia dengan rasa ingin tahu yang liar.",
         trailer="RlbR5N6veqw", color="#db2777"),
    dict(id="lalaland", title="La La Land", year=2016, duration=128,
         director="Damien Chazelle", actors=["Ryan Gosling", "Emma Stone"],
         genre=["Musical", "Romance", "Drama"], curator_score=8.6,
         synopsis="Kisah cinta seorang musisi jazz dan aktris yang berjuang mengejar impian di tengah gemerlap Los Angeles.",
         trailer="0pdqf4P9MB8", color="#db2777"),
]

# ---------------------------------------------------------
# 3. BANGUN GRAPH SEKALI SAAT SERVER START
# ---------------------------------------------------------
graph = MovieGraph()
for m in RAW_MOVIES:
    graph.add_movie(m)
graph.build_edges_from_attributes()


# ---------------------------------------------------------
# 4. ROUTES
# ---------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/movies")
def api_movies():
    data = [{"id": m["id"], "title": m["title"], "year": m["year"],
             "genre": m["genre"], "color": m["color"]} for m in RAW_MOVIES]
    data.sort(key=lambda x: x["title"])
    return jsonify(data)


@app.route("/api/movie/<movie_id>")
def api_movie_detail(movie_id):
    movie = graph.nodes.get(movie_id)
    if not movie:
        abort(404)
    return jsonify(movie)


@app.route("/api/recommend/<movie_id>")
def api_recommend(movie_id):
    if movie_id not in graph.nodes:
        abort(404)
    depth = int(request.args.get("depth", 2))
    top_n = int(request.args.get("top_n", 6))
    results = graph.weighted_recommendation(movie_id, depth=depth, top_n=top_n)
    return jsonify({
        "source": graph.nodes[movie_id],
        "recommendations": results,
    })


@app.route("/api/graph")
def api_graph_full():
    nodes, edges = graph.to_full_graph_json()
    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/graph/ego/<movie_id>")
def api_graph_ego(movie_id):
    if movie_id not in graph.nodes:
        abort(404)
    depth = int(request.args.get("depth", 1))
    node_ids, edges = graph.ego_graph(movie_id, depth=depth)
    nodes = [{"id": nid, "label": graph.nodes[nid]["title"],
              "color": graph.nodes[nid]["color"], "is_center": nid == movie_id}
             for nid in node_ids]
    edges_out = [{"from": e["from"], "to": e["to"], "relation": e["relation"],
                  "type": e["relation"].split(":")[0], "weight": e["weight"]} for e in edges]
    return jsonify({"nodes": nodes, "edges": edges_out})


@app.route("/api/path/<id1>/<id2>")
def api_path(id1, id2):
    if id1 not in graph.nodes or id2 not in graph.nodes:
        abort(404)
    path, edges = graph.bfs_shortest_path(id1, id2)
    if path is None:
        return jsonify({"connected": False})
    detail = [{"id": pid, "title": graph.nodes[pid]["title"], "color": graph.nodes[pid]["color"]} for pid in path]
    return jsonify({"connected": True, "path": detail, "edges": edges})


if __name__ == "__main__":
    import os
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000, use_reloader=debug_mode)
