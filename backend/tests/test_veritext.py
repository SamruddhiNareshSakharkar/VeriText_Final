import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.ml.ai_detector import ai_detector
from backend.app.ml.similarity_engine import similarity_engine
from backend.app.ml.handwriting_engine import handwriting_engine

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_auth_workflow():
    # 1. Register a teacher
    teacher_email = "prof.smith@veritext.edu"
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": teacher_email,
        "password": "Password123!",
        "full_name": "Prof. Smith",
        "role": "teacher"
    })
    # Either 201 or 400 if already created
    assert reg_resp.status_code in [201, 400]

    # 2. Login teacher
    login_resp = client.post("/api/v1/auth/login", json={
        "email": teacher_email,
        "password": "Password123!"
    })
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    teacher_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {teacher_token}"}

    # 3. Fetch profile
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == teacher_email
    assert me_resp.json()["role"] == "teacher"

    # 4. Create a team / course
    team_resp = client.post("/api/v1/teams", json={
        "name": "CS401: Advanced Algorithms",
        "description": "Graduate level algorithms and complexity analysis",
        "course_code": "CS-401"
    }, headers=headers)
    assert team_resp.status_code == 201
    team = team_resp.json()
    assert team["join_code"].startswith("VTX-")
    team_id = team["id"]
    join_code = team["join_code"]

    # 5. Register a student
    student_email = "alex.rivera@veritext.edu"
    stu_reg = client.post("/api/v1/auth/register", json={
        "email": student_email,
        "password": "StudentPassword456!",
        "full_name": "Alex Rivera",
        "role": "student"
    })
    assert stu_reg.status_code in [201, 400]

    stu_login = client.post("/api/v1/auth/login", json={
        "email": student_email,
        "password": "StudentPassword456!"
    })
    student_token = stu_login.json()["access_token"]
    stu_headers = {"Authorization": f"Bearer {student_token}"}

    # 6. Student joins team using join code
    join_resp = client.post("/api/v1/teams/join", json={"join_code": join_code}, headers=stu_headers)
    # 200 or 400 (if already member)
    assert join_resp.status_code in [200, 400]

    # 7. Student cannot join twice
    dup_join = client.post("/api/v1/teams/join", json={"join_code": join_code}, headers=stu_headers)
    assert dup_join.status_code == 400

    # 8. Teacher creates assignment in team
    assign_resp = client.post(f"/api/v1/teams/{team_id}/assignments", json={
        "title": "Problem Set 1: Dynamic Programming Proofs",
        "description": "Submit mathematical derivations and complexity proofs.",
        "max_marks": 100.0,
        "allowed_file_types": "pdf,txt,docx"
    }, headers=headers)
    assert assign_resp.status_code == 201
    assignment = assign_resp.json()
    assignment_id = assignment["id"]

    # 9. Student views assignments
    student_assignments = client.get("/api/v1/assignments", headers=stu_headers)
    assert student_assignments.status_code == 200
    found = any(a["id"] == assignment_id for a in student_assignments.json())
    assert found is True

def test_ml_ai_detector():
    # Human text sample with high burstiness and natural stylistic variation
    human_sample = (
        "We started the experiment at dawn. Rain was pounding against the lab windows, making it hard "
        "to hear the spectrometer calibrate. But Dr. Vance didn't care at all. He just kept pouring the saline. "
        "Why did the temperature drop so suddenly? Nobody had an answer. By noon, however, the precipitation had stopped, "
        "and our readings stabilized."
    )
    human_res = ai_detector.analyze_text(human_sample)
    assert "score" in human_res
    assert "detected_spans" in human_res
    assert human_res["score"] < 50.0  # Should be low AI likelihood

    # AI-style text sample with formulaic transitions and uniform sentence rhythms
    ai_sample = (
        "In conclusion, it is important to note that the emergence of quantum computing plays a pivotal role "
        "in modern cybersecurity paradigms. Furthermore, by delving into the algorithmic intricacies of cryptographic keys, "
        "researchers can effectively mitigate systemic vulnerabilities. Moreover, this technological milestone stands as a testament to "
        "human ingenuity while navigating the complexities of computational resilience in an evolving technological landscape."
    )
    ai_res = ai_detector.analyze_text(ai_sample)
    assert ai_res["score"] > 35.0
    assert len(ai_res["detected_spans"]) > 0

def test_ml_similarity_engine():
    doc_1 = "Dynamic programming solves complex problems by breaking them down into simpler subproblems and storing the intermediate solutions to avoid redundant computations."
    doc_2 = "Dynamic programming solves complex problems by breaking them down into simpler subproblems and storing the intermediate solutions in memory for lookup."
    doc_3 = "The photosynthesis process converts photon energy into glucose within plant chloroplasts using carbon dioxide and water."

    sim_high = similarity_engine.compare_documents(doc_1, doc_2)
    assert sim_high["score"] > 50.0
    assert len(sim_high["matching_segments"]) > 0

    sim_low = similarity_engine.compare_documents(doc_1, doc_3)
    assert sim_low["score"] < 25.0

def test_ml_handwriting_engine():
    features_a = [0.15, 0.22, 0.45, 0.78, 0.33, 0.12, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    features_b = [0.16, 0.21, 0.44, 0.77, 0.34, 0.13, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    features_c = [-0.8, 0.9, 0.1, 0.2, 0.8, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]

    sim_close = handwriting_engine.compare_handwriting(features_a, features_b)
    sim_diff = handwriting_engine.compare_handwriting(features_a, features_c)
    assert sim_close > 90.0
    assert sim_close > sim_diff
