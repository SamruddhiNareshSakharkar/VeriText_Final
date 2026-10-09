from backend.app.ml.ai_detector import ai_detector

cases = [
    ("Human Essay", """During my summer internship at the local manufacturing plant, I worked closely with the quality assurance team. Every morning, we inspected the assembly lines and verified that the components met our safety specifications. One major challenge we faced was an unexpected delay in the supply chain for micro-controllers. Because of this, our team had to quickly redesign the testing protocol to accommodate alternative parts. In the end, we managed to deliver the prototype on time, which was a huge relief for everyone involved."""),

    ("100% AI Essay", """Artificial intelligence (AI) has emerged as a transformative force across various sectors, significantly altering how individuals interact with technology and process information. In contemporary society, machine learning algorithms and neural networks play a pivotal role in automating complex tasks, enhancing decision-making capabilities, and driving innovation across diverse domains. From healthcare diagnostics to autonomous transportation, the integration of intelligent systems facilitates unprecedented levels of efficiency and precision.

Furthermore, generative artificial intelligence represents a paradigm shift in human-computer interaction. By leveraging massive natural language processing models, these systems can synthesize complex ideas, generate coherent prose, and assist in creative problem-solving. However, the ubiquitous deployment of such technologies also introduces critical ethical considerations, including data privacy, algorithmic bias, and academic integrity. As society navigates this evolving technological landscape, it is imperative to establish robust regulatory frameworks that balance innovation with ethical responsibility, ensuring that technological advancements serve the collective benefit of humanity."""),

    ("AI Assignment (Computer Science)", """Data Structures and Algorithms form the foundational bedrock of modern software engineering. Efficient algorithms optimize computational complexity and resource utilization, which plays a crucial role in scalable system architectures.

Linear vs Non-Linear Data Structures
Linear data structures, such as arrays and linked lists, organize elements sequentially. In contrast, non-linear structures like trees and graphs model hierarchical and networked relationships. For example, binary search trees enable logarithmic time complexity for search operations under balanced conditions.

Conclusion
In conclusion, selecting appropriate data structures is vital for software performance engineering. A thorough understanding of algorithmic efficiency empowers developers to design robust and scalable applications in an increasingly digital world."""),

    ("Mixed Assignment (Half Human / Half AI)", """I started this research project because I noticed how difficult it was for students in our hostel to find good study materials. My roommate and I conducted a survey with 45 classmates to understand their daily study habits and pain points.

However, artificial intelligence plays a pivotal role in revolutionizing contemporary educational methodologies. By leveraging adaptive learning algorithms, digital platforms provide personalized instructional pathways tailored to individual student needs, fostering heightened engagement and academic achievement across the technological landscape.""")
]

if __name__ == "__main__":
    for name, text in cases:
        res = ai_detector.analyze_text(text)
        print(f"\n==================== [{name}] ====================")
        print(f"AI Score: {res['score']}% | Classification: {res['classification']} | Confidence: {res['confidence']}%")
        print(f"Burstiness: {res['burstiness']}% | Perplexity: {res['perplexity']}")
        print(f"Flagged Spans Count: {len(res['detected_spans'])}")
        for i, s in enumerate(res['detected_spans']):
            print(f"  [{i+1}] ({s['confidence']*100:.0f}%) '{s['text'][:65]}...' -> {s['reason']}")
