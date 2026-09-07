# application loading lag when crolling, fix it. design lag, card stuck adn then load. also certificate catagorize. achivement , partificaption certificate and lern certificate. then each one slick then relevent  certificate need to appire.

from pathlib import Path
from imagekitio import ImageKit

imagekit = ImageKit(
    private_key="private_5cDwgSe8Ss2Rlk9HotSK77RoQM8="
)

URL_ENDPOINT = "https://ik.imagekit.io/x2eerczu0"

def upload_image(file_path: str, folder: str = "/portfolio/hero"):
    p = Path(file_path)

    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not p.is_file():
        raise ValueError(f"Not a file: {file_path}")

    response = imagekit.files.upload(
        file=p,
        file_name=p.name,
        folder=folder,
        use_unique_file_name=True,
        tags=["portfolio", "upload"]
    )

    print("Upload successful")
    print("URL:", response.url)
    print("File ID:", response.file_id)
    print("Name:", response.name)
    print("Folder:", folder)
    print("Endpoint:", URL_ENDPOINT)

    return response


if __name__ == "__main__":
    path = input("Enter full image path: ").strip().strip('"')
    folder = input("Enter folder name (example: /portfolio/hero): ").strip() or "/portfolio/hero"
    upload_image(path, folder)