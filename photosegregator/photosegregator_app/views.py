import os
import json
import shutil
import zipfile
import tempfile
import base64
import numpy as np
import requests
from io import BytesIO
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, FileResponse, HttpResponseBadRequest, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Event

# ── FACE DETECTION (install: pip install deepface) ───────────────
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

# ── QR CODE (install: pip install qrcode pillow) ──────────────
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

# ── SCIPY (install: pip install scipy) ──────────────────────
try:
    from scipy.spatial.distance import cosine
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════════════
# ══ R12 SERVER HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def _get_gallery_images_from_r12(event_code):
    """
    Fetch image list from R12 server using list.php
    
    Args:
        event_code: Event code to fetch images for
    
    Returns:
        List of image filenames or empty list on error
    """
    try:
        list_url = f"{settings.GALLERY_LIST_PHP}?event={event_code}"
        print(f"[R12] Fetching image list from: {list_url}")
        
        response = requests.get(list_url, timeout=10)
        
        if response.status_code == 200:
            images = response.json()
            print(f"[R12] ✅ Got {len(images)} images from R12")
            return images
        else:
            print(f"[R12] ❌ HTTP {response.status_code}")
            return []
    
    except requests.exceptions.Timeout:
        print(f"[R12] ❌ Timeout connecting to R12 server")
        return []
    except requests.exceptions.ConnectionError:
        print(f"[R12] ❌ Cannot connect to R12 server")
        return []
    except json.JSONDecodeError:
        print(f"[R12] ❌ Invalid JSON response from R12")
        return []
    except Exception as e:
        print(f"[R12] ❌ Error: {e}")
        return []


def _download_image_from_r12(event_code, filename):
    """
    Download image from R12 server and save to temp location
    
    Args:
        event_code: Event code
        filename: Image filename
    
    Returns:
        Temp file path or None on error
    """
    try:
        image_url = f"{settings.GALLERY_BASE_URL}/{event_code}/{filename}"
        print(f"[R12] Downloading: {image_url}")
        
        response = requests.get(image_url, timeout=10)
        
        if response.status_code == 200:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(response.content)
                temp_path = tmp.name
            
            print(f"[R12] ✅ Downloaded {filename} to {temp_path}")
            return temp_path
        else:
            print(f"[R12] ❌ HTTP {response.status_code} for {filename}")
            return None
    
    except requests.exceptions.Timeout:
        print(f"[R12] ❌ Timeout downloading {filename}")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[R12] ❌ Cannot connect to R12 for {filename}")
        return None
    except Exception as e:
        print(f"[R12] ❌ Error downloading {filename}: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# ══ EVENT MANAGER PAGES
# ════════════════════════════════════════════════════════════════════════════

def event_manager_home(request):
    """Event manager landing page - create new events"""
    print("[DEBUG] event_manager_home called")
    return render(request, 'photosegregator_app/event_manager.html')


def event_details(request, event_code):
    """Show event details, QR code, and link for sharing"""
    print(f"[DEBUG] event_details called for {event_code}")
    
    event = get_object_or_404(Event, event_code=event_code, is_active=True)
    
    # Build the event guest link
    request_host = request.get_host()
    # guest_link = f"http://{request_host}/event/{event_code}/"
    guest_link = f"http://{request_host}/event/{event_code}/guest/"
    
    print(f"[DEBUG] Guest link: {guest_link}")
    
    # Generate QR code as base64 if available
    qr_image_b64 = None
    if QRCODE_AVAILABLE:
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(guest_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_image_b64 = base64.b64encode(buffer.getvalue()).decode()
            print("[DEBUG] QR code generated successfully")
        except Exception as e:
            print(f"[ERROR] QR generation failed: {e}")
    else:
        print("[WARNING] QRCode not available")
    
    context = {
        'event': event,
        'guest_link': guest_link,
        'qr_image_b64': qr_image_b64,
    }
    return render(request, 'photosegregator_app/event_details.html', context)


def event_guest_page(request, event_code):
    """Guest-facing photo upload page for a specific event"""
    print(f"[DEBUG] event_guest_page called for {event_code}")
    
    event = get_object_or_404(Event, event_code=event_code, is_active=True)
    context = {'event': event}
    return render(request, 'photosegregator_app/event_guest.html', context)


# ════════════════════════════════════════════════════════════════════════════
# ══ API: EVENT CREATION
# ════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def api_create_event(request):
    """
    POST /api/event/create/
    
    Request body:
    {
        "event_name": "Sharma Wedding",
        "manager_name": "Amit Sharma"
    }
    
    Response:
    {
        "success": true,
        "event_code": "EVT4K9X2",
        "guest_link": "http://domain.com/event/EVT4K9X2/"
    }
    """
    print("[DEBUG] api_create_event called")
    
    try:
        data = json.loads(request.body)
        event_name = data.get('event_name', '').strip()
        manager_name = data.get('manager_name', '').strip()
        
        print(f"[DEBUG] Event name: {event_name}, Manager: {manager_name}")
        
        if not event_name or not manager_name:
            return JsonResponse({
                'success': False,
                'error': 'Event name and manager name are required.'
            }, status=400)
        
        # Create event
        event = Event.objects.create(
            event_name=event_name,
            manager_name=manager_name
        )
        
        print(f"[DEBUG] Event created: {event.event_code}")
        
        request_host = request.get_host()
        guest_link = f"http://{request_host}/event/{event.event_code}/"
        
        return JsonResponse({
            'success': True,
            'event_code': event.event_code,
            'guest_link': guest_link,
        })
    
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON format'
        }, status=400)
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ════════════════════════════════════════════════════════════════════════════
# ══ ROBUST FACE DETECTION & MATCHING
# ════════════════════════════════════════════════════════════════════════════

def _get_face_embedding(image_path, detectors=None):
    """
    Get face embedding from image using multiple detectors with fallback.
    
    Args:
        image_path: Path to image file
        detectors: List of detector backends to try
    
    Returns:
        embedding (numpy array) or None if no face detected
    """
    if detectors is None:
        detectors = ["retinaface", "mtcnn", "mediapipe", "ssd", "dlib"]
    
    model = "ArcFace"  # Consistent 512-dim embeddings
    
    for detector in detectors:
        try:
            result = DeepFace.represent(
                img_path=image_path,
                model_name=model,
                detector_backend=detector,
                enforce_detection=True,
            )
            
            if result and len(result) > 0:
                print(f"  ✅ {detector}: Face detected")
                return np.array(result[0]['embedding'])
        
        except Exception as e:
            error_msg = str(e).lower()
            if 'face' in error_msg and 'detect' in error_msg:
                print(f"  ⚠️  {detector}: No face")
            else:
                print(f"  ⚠️  {detector}: {type(e).__name__}")
            continue
    
    return None


def _calculate_cosine_similarity(embedding1, embedding2):
    """
    Calculate cosine similarity between two embeddings.
    
    Args:
        embedding1: First embedding (numpy array)
        embedding2: Second embedding (numpy array)
    
    Returns:
        Similarity score 0-100 (higher = more similar)
    """
    try:
        # Cosine similarity returns -1 to 1; convert to 0-100
        cosine_dist = cosine(embedding1, embedding2)
        similarity = (1 - cosine_dist) * 100
        return float(max(0, min(100, similarity)))
    except Exception as e:
        print(f"[ERROR] Similarity calculation failed: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# ══ API: PHOTO FINDING (EVENT-AWARE) - WITH R12 INTEGRATION
# ════════════════════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def api_find_my_photos_event(request, event_code):
    """
    POST /api/event/{event_code}/find-my-photos/
    
    Find all photos matching a person's face in the event gallery on R12 server.
    
    Uses:
    ✅ DeepFace ArcFace (512-dim embeddings)
    ✅ Multiple detector backends (retinaface, mtcnn, mediapipe, ssd, dlib)
    ✅ Cosine similarity (better than euclidean for face embeddings)
    ✅ Adaptive threshold based on top matches
    ✅ R12 Server integration for photo storage
    
    Request:
    - Multipart form with 'selfie' file
    
    Response:
    {
        'success': true,
        'matched': true/false,
        'total_photos': N,
        'confidence': 0-100,
        'person_label': 'detected_person',
        'matched_photos': [{'filename': 'x.jpg', 'score': 75.3}, ...]
    }
    """
    print(f"\n{'='*70}")
    print(f"🎯 API: find_my_photos_event for {event_code}")
    print(f"{'='*70}\n")
    
    # ════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════
    
    if not DEEPFACE_AVAILABLE:
        print("❌ DeepFace not available")
        return JsonResponse({
            'success': False,
            'error': 'DeepFace not installed. Run: pip install deepface'
        }, status=500)
    
    if not SCIPY_AVAILABLE:
        print("❌ SciPy not available")
        return JsonResponse({
            'success': False,
            'error': 'SciPy not installed. Run: pip install scipy'
        }, status=500)
    
    try:
        event = Event.objects.get(event_code=event_code, is_active=True)
    except Event.DoesNotExist:
        print(f"❌ Event {event_code} not found")
        return JsonResponse({
            'success': False,
            'error': 'Event not found'
        }, status=404)
    
    if not request.FILES.get('selfie'):
        print("❌ No selfie file provided")
        return JsonResponse({
            'success': False,
            'error': 'No selfie file provided'
        }, status=400)
    
    selfie_file = request.FILES['selfie']
    selfie_path = None
    downloaded_images = []  # Track temp files for cleanup
    
    try:
        # ════════════════════════════════════════════════════════════════
        # SETUP
        # ════════════════════════════════════════════════════════════════
        
        # Save selfie temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            for chunk in selfie_file.chunks():
                tmp.write(chunk)
            selfie_path = tmp.name
        
        print(f"📷 Selfie saved to: {selfie_path}")
        
        # ════════════════════════════════════════════════════════════════
        # STEP 1: Get selfie embedding
        # ════════════════════════════════════════════════════════════════
        
        print("Step 1️⃣  : Detecting face in selfie...")
        selfie_embedding = _get_face_embedding(selfie_path)
        
        if selfie_embedding is None:
            print("❌ Could not detect face in selfie")
            return JsonResponse({
                'success': False,
                'error': 'Could not detect your face. Try a clearer photo with better lighting.'
            }, status=400)
        
        print(f"✅ Selfie embedding generated (size: {len(selfie_embedding)})\n")
        
        # ════════════════════════════════════════════════════════════════
        # STEP 2: Get image list from R12 server
        # ════════════════════════════════════════════════════════════════
        
        print(f"Step 2️⃣  : Fetching image list from R12 server...")
        images = _get_gallery_images_from_r12(event_code)
        
        if not images:
            print("⚠️  No images found on R12 server")
            return JsonResponse({
                'success': True,
                'matched': False,
                'message': 'No images in gallery. Please upload photos first.'
            })
        
        print(f"✅ Got {len(images)} images from R12\n")
        
        # ════════════════════════════════════════════════════════════════
        # STEP 3: Download and compare with ALL gallery images
        # ════════════════════════════════════════════════════════════════
        
        print(f"Step 3️⃣  : Comparing with {len(images)} gallery images...")
        all_scores = []  # Track all scores for adaptive threshold
        
        for idx, img_file in enumerate(images, 1):
            # Download image from R12
            img_temp_path = _download_image_from_r12(event_code, img_file)
            
            if img_temp_path is None:
                print(f"  ⚠️  {img_file}: Could not download")
                continue
            
            downloaded_images.append(img_temp_path)
            
            try:
                # Get gallery image embedding
                gallery_embedding = _get_face_embedding(img_temp_path)
                
                if gallery_embedding is None:
                    # Skip images without detectable faces
                    print(f"  ⚠️  {img_file}: No face detected")
                    continue
                
                # Calculate similarity
                score = _calculate_cosine_similarity(selfie_embedding, gallery_embedding)
                
                if score is None:
                    continue
                
                all_scores.append((img_file, score))
                
                # Print progress
                if idx % 5 == 0 or score >= 50:
                    status = "✅" if score >= 50 else "⚠️"
                    print(f"  [{idx:3d}/{len(images)}] {status} {img_file}: {score:.1f}%")
            
            except Exception as e:
                print(f"  ⚠️  {img_file}: {type(e).__name__}")
                continue
        
        # Sort by score descending
        all_scores.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\nTotal images with detectable faces: {len(all_scores)}")
        
        # ════════════════════════════════════════════════════════════════
        # STEP 4: Smart threshold - take top matches AND anything above 40%
        # ════════════════════════════════════════════════════════════════
        
        if not all_scores:
            print("⚠️  No faces detected in gallery")
            return JsonResponse({
                'success': True,
                'matched': False,
                'message': 'No detectable faces in gallery images'
            })
        
        # Strategy: Take top 20% of matches OR anything >= 40% similarity
        top_count = max(1, len(all_scores) // 5)  # Top 20%
        threshold = 40.0
        
        matched_photos = []
        for filename, score in all_scores:
            if len(matched_photos) < top_count or score >= threshold:
                matched_photos.append((filename, score))
            else:
                break  # Since sorted, rest will be lower
        
        print(f"\n{'='*70}")
        print(f"📊 RESULTS")
        print(f"{'='*70}")
        print(f"Total images scanned: {len(images)}")
        print(f"Faces detected: {len(all_scores)}")
        print(f"Matches found (top 20% or ≥40%): {len(matched_photos)}")
        
        if matched_photos:
            print(f"\n🎯 Top matches:")
            for i, (filename, score) in enumerate(matched_photos[:10], 1):
                print(f"  {i}. {filename}: {score:.1f}%")
        
        print(f"{'='*70}\n")
        
        # No matches
        if not matched_photos:
            return JsonResponse({
                'success': True,
                'matched': False,
                'message': f'No strong matches found'
            })
        
        # Return matches
        scores = [f[1] for f in matched_photos]
        avg_confidence = np.mean(scores) if scores else 0
        
        return JsonResponse({
            'success': True,
            'matched': True,
            'message': f'Found {len(matched_photos)} matching photos',
            'total_photos': len(matched_photos),
            'confidence': round(avg_confidence, 1),
            'person_label': 'detected_person',
            'matched_photos': [
                {
                    'filename': f[0],
                    'score': round(f[1], 1)
                }
                for f in matched_photos
            ]
        })
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }, status=500)
    
    finally:
        # Cleanup temp files
        try:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
        except:
            pass
        
        for img_path in downloaded_images:
            try:
                if img_path and os.path.exists(img_path):
                    os.remove(img_path)
            except:
                pass
        
        print("🧹 Temp files cleaned up")


# ════════════════════════════════════════════════════════════════════════════
# ══ API: PHOTO SERVING (Proxy from R12)
# ════════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def api_serve_photo_event(request, event_code, filename):
    """GET /api/event/{event_code}/photo/{filename}/
    
    Proxy photo from R12 server to client
    """
    print(f"[DEBUG] Serving photo {filename} from event {event_code}")
    
    try:
        event = Event.objects.get(event_code=event_code, is_active=True)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    
    # Security check
    if '/' in filename or '\\' in filename or '..' in filename:
        return HttpResponseBadRequest("Invalid filename")
    
    try:
        photo_url = f"{settings.GALLERY_BASE_URL}/{event_code}/{filename}"
        print(f"[R12] Proxying: {photo_url}")
        
        response = requests.get(photo_url, stream=True, timeout=10)
        
        if response.status_code == 200:
            return StreamingHttpResponse(
                response.iter_content(chunk_size=8192),
                content_type=response.headers.get('content-type', 'image/jpeg')
            )
        else:
            print(f"[R12] ❌ HTTP {response.status_code}")
            return HttpResponseBadRequest("Photo not found")
    
    except requests.exceptions.Timeout:
        print(f"[R12] ❌ Timeout")
        return HttpResponseBadRequest("R12 server timeout")
    except requests.exceptions.ConnectionError:
        print(f"[R12] ❌ Connection error")
        return HttpResponseBadRequest("Cannot connect to R12 server")
    except Exception as e:
        print(f"[ERROR] {e}")
        return HttpResponseBadRequest("Could not serve photo")


# ════════════════════════════════════════════════════════════════════════════
# ══ API: PHOTO DOWNLOAD (Single)
# ════════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def api_download_photo_event(request, event_code, filename):
    """GET /api/event/{event_code}/download/{filename}/
    
    Download single photo from R12 server
    """
    print(f"[DEBUG] Downloading photo {filename} from event {event_code}")
    
    try:
        event = Event.objects.get(event_code=event_code, is_active=True)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    
    # Security check
    if '/' in filename or '\\' in filename or '..' in filename:
        return HttpResponseBadRequest("Invalid filename")
    
    try:
        photo_url = f"{settings.GALLERY_BASE_URL}/{event_code}/{filename}"
        response = requests.get(photo_url, timeout=10)
        
        if response.status_code == 200:
            return FileResponse(
                BytesIO(response.content),
                as_attachment=True,
                filename=filename,
                content_type='image/jpeg'
            )
        else:
            return HttpResponseBadRequest("Photo not found")
    
    except Exception as e:
        print(f"[ERROR] {e}")
        return HttpResponseBadRequest("Could not download photo")


# ════════════════════════════════════════════════════════════════════════════
# ══ API: PHOTO DOWNLOAD (Multiple as ZIP)
# ════════════════════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def api_download_all_photos_event(request, event_code):
    """GET /api/event/{event_code}/download-all/?files=file1.jpg,file2.jpg"""
    print(f"[DEBUG] Downloading all photos from event {event_code}")
    
    try:
        event = Event.objects.get(event_code=event_code, is_active=True)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    
    filenames = request.GET.get('files', '').split(',')
    
    try:
        # Create zip
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in filenames:
                filename = filename.strip()
                
                # Security check
                if not filename or '/' in filename or '\\' in filename or '..' in filename:
                    continue
                
                try:
                    photo_url = f"{settings.GALLERY_BASE_URL}/{event_code}/{filename}"
                    response = requests.get(photo_url, timeout=10)
                    
                    if response.status_code == 200:
                        zf.writestr(filename, response.content)
                        print(f"[DEBUG] Added to ZIP: {filename}")
                except Exception as e:
                    print(f"[WARNING] Could not add {filename}: {e}")
                    continue
        
        zip_buffer.seek(0)
        return FileResponse(
            zip_buffer,
            as_attachment=True,
            filename=f"{event.event_code}_photos.zip",
            content_type='application/zip'
        )
    
    except Exception as e:
        print(f"[ERROR] Error creating ZIP: {e}")
        return HttpResponseBadRequest("Could not create ZIP file")