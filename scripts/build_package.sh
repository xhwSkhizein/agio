#!/bin/bash
set -e

echo "🔨 Building Agio package..."

python -m pip install --upgrade build twine

echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info
rm -rf agio/frontend

echo "🌐 Building frontend..."
if [ -d "agio-frontend" ]; then
    if ! command -v npm &> /dev/null; then
        echo "⚠️  Warning: npm not found, skipping frontend build"
        echo "   Frontend will not be included in the package"
    else
        cd agio-frontend
        
        if [ ! -d "node_modules" ]; then
            echo "📦 Installing frontend dependencies..."
            npm install
        fi
        
        echo "🔨 Building frontend production bundle..."
        if npm run build; then
            cd ..
            
            echo "📁 Copying frontend dist to package..."
            mkdir -p agio/frontend
            cp -r agio-frontend/dist agio/frontend/
            
            echo "✅ Frontend built and copied"
        else
            cd ..
            echo "⚠️  Warning: Frontend build failed, continuing without frontend"
        fi
    fi
else
    echo "⚠️  Warning: agio-frontend directory not found, skipping frontend build"
fi

echo "📦 Building Python package..."
python -m build

echo "✅ Build complete! Distribution files are in dist/"
ls -lh dist/
