'''
RunPod | serverless-ckpt-template | runpod_infer.py

Entry point for job requests from RunPod serverless platform.
'''

import os
import argparse

import sd_runner

import runpod
from runpod.serverless.utils import rp_download, rp_cleanup, rp_upload
from runpod.serverless.utils.rp_validator import validate

INPUT_SCHEMA = {
    'prompt': {
        'type': str,
        'required': True
    },
    'negative_prompt': {
        'type': str,
        'required': False,
        'default': None
    },
    'width': {
        'type': int,
        'required': False,
        'default': 768,
        'constraints': lambda width: width in [128, 256, 384, 448, 512, 576, 640, 704, 768, 832, 896, 960, 1024]
    },
    'height': {
        'type': int,
        'required': False,
        'default': 768,
        'constraints': lambda height: height in [128, 256, 384, 448, 512, 576, 640, 704, 768, 832, 896, 960, 1024]
    },
    'num_outputs': {
        'type': int,
        'required': False,
        'default': 1,
        'constraints': lambda num_outputs: num_outputs in range(1, 4)
    },
    'num_inference_steps': {
        'type': int,
        'required': False,
        'default': 50,
        'constraints': lambda num_inference_steps: num_inference_steps in range(1, 500)
    },
    'guidance_scale': {
        'type': float,
        'required': False,
        'default': 7.5,
        'constraints': lambda guidance_scale: 0 <= guidance_scale <= 20
    },
    'scheduler': {
        'type': str,
        'required': False,
        'default': 'DPMSolverMultistep',
        'constraints': lambda scheduler: scheduler in ['DDIM', 'K_EULER', 'DPMSolverMultistep', 'K_EULER_ANCESTRAL', 'PNDM', 'KLMS']
    },
    'seed': {
        'type': int,
        'required': False,
        'default': int.from_bytes(os.urandom(2), "big")
    }
}


def handler(job):
    '''
    Takes in raw data from the API call, prepares it for the model.
    Passes the data to the model to get the results.
    Prepares the resulting output to be returned to the API call.
    '''
    job_input = job['input']
    job_output = []

    # Health check endpoint
    if job_input.get('health_check'):
        return {"status": "healthy", "model_loaded": hasattr(model_runner, 'pipe')}

    # -------------------------------- Validation -------------------------------- #
    validated_input = validate(job_input, INPUT_SCHEMA)
    if 'errors' in validated_input:
        return {"errors": validated_input['errors']}

    valid_input = validated_input['validated_input']

    try:
        image_paths = model_runner.predict(
            prompt=valid_input['prompt'],
            negative_prompt=valid_input['negative_prompt'],
            width=valid_input['width'],
            height=valid_input['height'],
            num_outputs=valid_input['num_outputs'],
            num_inference_steps=valid_input['num_inference_steps'],
            guidance_scale=valid_input['guidance_scale'],
            scheduler=valid_input['scheduler'],
            seed=valid_input['seed']
        )

        for index, img_path in enumerate(image_paths):
            image_url = rp_upload.upload_image(job['id'], img_path)

            job_output.append({
                "image": image_url,
                "prompt": job_input["prompt"],
                "negative_prompt": job_input["negative_prompt"],
                "width": job_input['width'],
                "height": job_input['height'],
                "num_inference_steps": job_input['num_inference_steps'],
                "guidance_scale": job_input['guidance_scale'],
                "scheduler": job_input['scheduler'],
                "seed": job_input['seed'] + index
            })

        # Remove downloaded input objects
        # rp_cleanup.clean(['input_objects'])

        return job_output
        
    except Exception as e:
        print(f"❌ Error during inference: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------- #
#                                     Main                                     #
# ---------------------------------------------------------------------------- #
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model_url", type=str,
                    default=None, help="Direct URL to safetensors model")
parser.add_argument("--base_model", type=str,
                    default="runwayml/stable-diffusion-v1-5", 
                    help="Base model to use (SD 1.5, SD 2.1, or SDXL)")


if __name__ == "__main__":
    args = parser.parse_args()
    
    print("🔧 Initializing RunPod handler...")
    print(f"📦 Model URL: {args.model_url}")
    print(f"🎯 Base Model: {args.base_model}")

    try:
        # Initialize the predictor with the specified base model
        print("🤖 Creating model predictor...")
        model_runner = sd_runner.Predictor(base_model=args.base_model)
        
        print("⚙️ Setting up model (this may take several minutes)...")
        model_runner.setup()
        
        print("✅ Model setup completed successfully!")
        print("🚀 Starting RunPod serverless handler...")
        
        runpod.serverless.start({"handler": handler})
        
    except Exception as e:
        print(f"❌ Fatal error during initialization: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
