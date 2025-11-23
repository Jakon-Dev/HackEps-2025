import os
import sys
import django
import sys
import os
import django

# Open log file immediately
with open('debug_output.txt', 'w', encoding='utf-8') as f:
    sys.stdout = f
    sys.stderr = f
    
    print("Starting test script...")
    
    try:
        import traceback
        
        print(f"CWD: {os.getcwd()}")
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hackeps25.settings')
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        print("Setting up Django...")
        django.setup()
        print("Django setup complete.")
        
        from principal.custom_recommendation import CustomRecommendationEngine

        print("=" * 60)
        print("Testing CustomRecommendationEngine")
        print("=" * 60)

        engine = CustomRecommendationEngine()
        print(f"\n✓ Engine initialized")
        
        data_count = len(engine.neighborhood_data)
        print(f"✓ Neighborhood data loaded: {data_count} neighborhoods")
        
        if data_count > 0:
            print("  - Sample neighborhood:", list(engine.neighborhood_data.keys())[0])
        else:
            print("  ❌ No neighborhood data loaded!")
            
        metrics_count = len(engine.json_metrics)
        print(f"✓ Metrics JSON loaded: {metrics_count} neighborhoods")
        
        if data_count > 0 and metrics_count > 0:
            print("\n✅ SUCCESS: CustomRecommendationEngine is working correctly!")
        else:
            print("\n❌ FAILURE: Data loading failed.")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()

    print("Script finished.")
    
    # Restore stdout/stderr
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
