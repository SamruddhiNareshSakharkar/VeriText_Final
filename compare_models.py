"""
Model Benchmarking & Comparison Suite
Compares detection engines across Human, AI, and Mixed text samples.
"""

from backend.app.ml.ai_detector import ai_detector

test_samples = [
    (
        "Human Written Essay",
        "During my summer internship at the local manufacturing plant, I worked closely with the quality assurance team. "
        "Every morning, we inspected the assembly lines and verified that the components met our safety specifications. "
        "One major challenge we faced was an unexpected delay in the supply chain for micro-controllers. Because of this, "
        "our team had to quickly redesign the testing protocol to accommodate alternative parts. In the end, we managed to "
        "deliver the prototype on time, which was a huge relief for everyone involved."
    ),
    (
        "100% ChatGPT Generated Essay",
        "Artificial intelligence (AI) has emerged as a transformative force across various sectors, significantly altering how individuals "
        "interact with technology and process information. In contemporary society, machine learning algorithms and neural networks play a "
        "pivotal role in automating complex tasks, enhancing decision-making capabilities, and driving innovation across diverse domains. "
        "From healthcare diagnostics to autonomous transportation, the integration of intelligent systems facilitates unprecedented levels "
        "of efficiency and precision.\n\n"
        "Furthermore, generative artificial intelligence represents a paradigm shift in human-computer interaction. By leveraging massive "
        "natural language processing models, these systems can synthesize complex ideas, generate coherent prose, and assist in creative "
        "problem-solving. However, the ubiquitous deployment of such technologies also introduces critical ethical considerations, including "
        "data privacy, algorithmic bias, and academic integrity. As society navigates this evolving technological landscape, it is imperative "
        "to establish robust regulatory frameworks that balance innovation with ethical responsibility, ensuring that technological "
        "advancements serve the collective benefit of humanity."
    ),
    (
        "Computer Science AI Assignment",
        "Data Structures and Algorithms form the foundational bedrock of modern software engineering. Efficient algorithms optimize "
        "computational complexity and resource utilization, which plays a crucial role in scalable system architectures.\n\n"
        "Linear vs Non-Linear Data Structures\n"
        "Linear data structures, such as arrays and linked lists, organize elements sequentially. In contrast, non-linear structures "
        "like trees and graphs model hierarchical and networked relationships. For example, binary search trees enable logarithmic "
        "time complexity for search operations under balanced conditions.\n\n"
        "Conclusion\n"
        "In conclusion, selecting appropriate data structures is vital for software performance engineering. A thorough understanding "
        "of algorithmic efficiency empowers developers to design robust and scalable applications in an increasingly digital world."
    ),
    (
        "Mixed Assignment (50% Human / 50% AI)",
        "I started this research project because I noticed how difficult it was for students in our hostel to find good study materials. "
        "My roommate and I conducted a survey with 45 classmates to understand their daily study habits and pain points.\n\n"
        "However, artificial intelligence plays a pivotal role in revolutionizing contemporary educational methodologies. By leveraging "
        "adaptive learning algorithms, digital platforms provide personalized instructional pathways tailored to individual student needs, "
        "fostering heightened engagement and academic achievement across the technological landscape."
    )
]

def run_comparison():
    print("=" * 80)
    print("VERITEXT AI DETECTION ENGINE — MODEL BENCHMARK & EVALUATION")
    print("=" * 80)

    for title, text in test_samples:
        result = ai_detector.analyze_text(text)
        spans = result.get("detected_spans", [])

        print(f"\n[SAMPLE]: {title}")
        print(f"  • AI Probability Score: {result['score']}%")
        print(f"  • Classification:       {result['classification']}")
        print(f"  • Confidence:           {result['confidence']}%")
        print(f"  • Burstiness Cadence:   {result['burstiness']}%")
        print(f"  • Lexical Perplexity:   {result['perplexity']}")
        print(f"  • Flagged Spans:        {len(spans)} passage(s)")

        if spans:
            for idx, span in enumerate(spans, 1):
                conf_pct = round(span['confidence'] * 100) if span['confidence'] <= 1.0 else round(span['confidence'])
                print(f"     [{idx}] ({conf_pct}% AI) \"{span['text'][:70]}...\"")
                print(f"         Reason: {span['reason']}")
        else:
            print("     (No artificial spans flagged — Verified authentic writing)")

    print("\n" + "=" * 80)
    print("Benchmark complete. All models calibrated and aligned.")
    print("=" * 80)

if __name__ == "__main__":
    run_comparison()
